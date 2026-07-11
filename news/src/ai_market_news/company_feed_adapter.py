from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from typing import Any, Callable
from urllib.parse import urlparse

from .collector_common import CollectorError, build_public_record, require
from .live_http import HttpResult, RateLimiter, fetch_bytes, host_is_allowed


class TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].casefold()


def child_text(element: ET.Element, *names: str) -> str:
    wanted = {name.casefold() for name in names}
    for child in element:
        if local_name(child.tag) in wanted:
            return "".join(child.itertext()).strip()
    return ""


def entry_link(element: ET.Element) -> str:
    for child in element:
        if local_name(child.tag) != "link":
            continue
        href = str(child.attrib.get("href", "")).strip()
        relation = str(child.attrib.get("rel", "alternate")).casefold()
        if href and relation in {"", "alternate"}:
            return href
        text = "".join(child.itertext()).strip()
        if text:
            return text
    return ""


def clean_source_summary(value: str) -> str:
    parser = TextExtractor()
    try:
        parser.feed(value)
        parser.close()
    except Exception as exc:
        raise CollectorError("official feed summary contains invalid markup") from exc
    text = " ".join(" ".join(parser.parts).split())
    text = re.sub(r"\s+", " ", text).strip()
    require(bool(text), "official feed entry is missing a source-provided summary")
    return text[:600].rstrip()


def parse_feed_timestamp(value: str) -> datetime:
    text = str(value).strip()
    require(bool(text), "official feed entry is missing a publication timestamp")
    try:
        parsed = parsedate_to_datetime(text)
    except (TypeError, ValueError, OverflowError):
        iso = text[:-1] + "+00:00" if text.endswith("Z") else text
        try:
            parsed = datetime.fromisoformat(iso)
        except ValueError as exc:
            raise CollectorError(f"invalid official feed timestamp: {value!r}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def parse_collected_at(value: str) -> datetime:
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise CollectorError(f"invalid collection timestamp: {value!r}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def feed_entries(body: bytes) -> list[dict[str, str]]:
    try:
        root = ET.fromstring(body)
    except ET.ParseError as exc:
        raise CollectorError("official company feed is not valid XML") from exc

    entries: list[dict[str, str]] = []
    for element in root.iter():
        kind = local_name(element.tag)
        if kind not in {"item", "entry"}:
            continue
        title = child_text(element, "title")
        link = entry_link(element)
        identifier = child_text(element, "guid", "id") or link
        published = child_text(element, "pubdate", "published", "updated")
        summary = child_text(element, "description", "summary", "content") or title
        entries.append(
            {
                "title": title,
                "link": link,
                "identifier": identifier,
                "published": published,
                "summary": summary,
            }
        )
    require(bool(entries), "official company feed contains no RSS items or Atom entries")
    return entries


def validate_config(config: dict[str, Any]) -> list[dict[str, Any]]:
    require(config.get("schema_version") == "1.0.0", "unsupported official-source config schema")
    values = config.get("sources")
    require(isinstance(values, list) and values, "official-source config must contain sources")
    sources: list[dict[str, Any]] = []
    seen_tickers: set[str] = set()
    for index, value in enumerate(values):
        require(isinstance(value, dict), f"sources[{index}] must be an object")
        ticker = str(value.get("ticker", "")).strip().upper()
        source_name = str(value.get("source_name", "")).strip()
        feed_url = str(value.get("feed_url", "")).strip()
        allowed = value.get("allowed_hosts")
        require(bool(ticker and source_name and feed_url), f"sources[{index}] has missing required fields")
        require(isinstance(allowed, list) and allowed, f"sources[{index}].allowed_hosts must be a non-empty list")
        allowed_hosts = {str(host).strip().casefold() for host in allowed}
        require(all(allowed_hosts), f"sources[{index}] contains an empty allowed host")
        require(host_is_allowed(feed_url, allowed_hosts), f"sources[{index}] feed URL is not allowlisted")
        require(ticker not in seen_tickers, f"duplicate official-source ticker: {ticker}")
        seen_tickers.add(ticker)
        sources.append(
            {
                "ticker": ticker,
                "source_name": source_name,
                "feed_url": feed_url,
                "allowed_hosts": allowed_hosts,
            }
        )
    return sources


def collect_company_feeds_live(
    config: dict[str, Any],
    *,
    collected_at_utc: str,
    user_agent: str,
    lookback_days: int,
    fetcher: Callable[..., HttpResult] = fetch_bytes,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    require(bool(user_agent.strip()), "official company feed collection requires a user agent")
    require(1 <= lookback_days <= 30, "lookback_days must be between 1 and 30")
    sources = validate_config(config)
    collected_at = parse_collected_at(collected_at_utc)
    cutoff = collected_at - timedelta(days=lookback_days)
    limiter = RateLimiter(2.0)

    records: list[dict[str, Any]] = []
    failures: list[str] = []
    seen_ids: set[tuple[str, str]] = set()
    request_count = 0

    for source in sources:
        ticker = source["ticker"]
        try:
            result = fetcher(
                source["feed_url"],
                allowed_hosts=source["allowed_hosts"],
                user_agent=user_agent,
                accept="application/atom+xml, application/rss+xml, application/xml, text/xml",
                rate_limiter=limiter,
            )
            request_count += result.request_count
            for entry in feed_entries(result.body):
                published_at = parse_feed_timestamp(entry["published"])
                if published_at < cutoff or published_at > collected_at + timedelta(minutes=5):
                    continue
                link = entry["link"]
                require(host_is_allowed(link, source["allowed_hosts"]), "official release link left the allowlisted host")
                identifier = entry["identifier"].strip()
                require(bool(identifier), "official feed entry is missing an identifier")
                identity = (ticker, identifier)
                require(identity not in seen_ids, f"duplicate official release ID: {ticker}:{identifier}")
                seen_ids.add(identity)
                title = " ".join(entry["title"].split())
                require(bool(title), "official feed entry is missing a title")
                summary = clean_source_summary(entry["summary"])
                records.append(
                    build_public_record(
                        ticker=ticker,
                        published_at_utc=published_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
                        collected_at_utc=collected_at_utc,
                        source_type="company_release",
                        source_name=source["source_name"],
                        source_url=link,
                        headline=title,
                        summary=summary,
                        provider="official_company_source",
                        provider_article_id=identifier,
                        source_ticker=ticker,
                        filing_type=None,
                        event_identity=identifier,
                        primary_source=True,
                    )
                )
        except (CollectorError, KeyError, TypeError, ValueError):
            failures.append(f"official_company_source:{ticker}:collection_failed")

    records.sort(key=lambda row: (row["published_at_utc"], row["ticker"], row["provider_article_id"]))
    return records, {
        "schema_version": "1.0.0",
        "provider": "official_company_source",
        "request_count": request_count,
        "configured_source_count": len(sources),
        "record_count": len(records),
        "failures": sorted(set(failures)),
        "article_pages_fetched": False,
    }
