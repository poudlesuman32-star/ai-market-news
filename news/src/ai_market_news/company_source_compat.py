from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from typing import Any, Callable
from urllib.parse import urljoin

from . import company_feed_adapter as feed_adapter
from .collector_common import CollectorError, build_public_record, require
from .live_http import HttpResult, RateLimiter, fetch_bytes, host_is_allowed

_RELEASE_PATH_FRAGMENT = "/news-releases/news-release-details/"
_DATE_PATTERN = re.compile(
    r"\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
    r"\s+\d{1,2},\s+\d{4}\b",
    re.IGNORECASE,
)


class _ReleaseIndexParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.entries: list[dict[str, str]] = []
        self._current: dict[str, Any] | None = None
        self._in_release_link = False

    @staticmethod
    def _clean(parts: list[str]) -> str:
        return " ".join(" ".join(parts).split())

    def _finish_current(self) -> None:
        if self._current is None:
            return
        title = self._clean(self._current["title_parts"])
        tail = self._clean(self._current["tail_parts"])
        match = _DATE_PATTERN.search(tail)
        if title and match:
            summary = tail[match.end() :].strip()
            summary = summary.split("PDF Version", 1)[0].strip()
            if summary.startswith(title):
                summary = summary[len(title) :].strip(" :-")
            self.entries.append(
                {
                    "title": title,
                    "link": str(self._current["href"]),
                    "identifier": str(self._current["href"]),
                    "published": match.group(0),
                    "summary": summary or title,
                }
            )
        self._current = None
        self._in_release_link = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() != "a":
            return
        href = str(dict(attrs).get("href") or "").strip()
        if _RELEASE_PATH_FRAGMENT not in href:
            return
        self._finish_current()
        self._current = {"href": href, "title_parts": [], "tail_parts": []}
        self._in_release_link = True

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() == "a" and self._in_release_link:
            self._in_release_link = False

    def handle_data(self, data: str) -> None:
        if self._current is None or not data.strip():
            return
        key = "title_parts" if self._in_release_link else "tail_parts"
        self._current[key].append(data)

    def close(self) -> None:
        super().close()
        self._finish_current()


def parse_release_index(body: bytes, *, index_url: str) -> list[dict[str, str]]:
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError:
        text = body.decode("utf-8", errors="replace")
    parser = _ReleaseIndexParser()
    try:
        parser.feed(text)
        parser.close()
    except Exception as exc:
        raise CollectorError("official company release index contains invalid HTML") from exc
    require(bool(parser.entries), "official company release index contains no release entries")
    entries: list[dict[str, str]] = []
    seen: set[str] = set()
    for entry in parser.entries:
        link = urljoin(index_url, entry["link"])
        require(link not in seen, f"duplicate official release link: {link}")
        seen.add(link)
        entries.append({**entry, "link": link, "identifier": link})
    return entries


def parse_release_index_timestamp(value: str) -> datetime:
    text = " ".join(str(value).split())
    for pattern in ("%b %d, %Y", "%B %d, %Y"):
        try:
            return datetime.strptime(text, pattern).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    raise CollectorError(f"invalid official release index timestamp: {value!r}")


def _split_sources(config: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    require(config.get("schema_version") == "1.0.0", "unsupported official-source config schema")
    values = config.get("sources")
    require(isinstance(values, list) and values, "official-source config must contain sources")
    feed_sources: list[dict[str, Any]] = []
    html_sources: list[dict[str, Any]] = []
    seen_tickers: set[str] = set()
    for index, value in enumerate(values):
        require(isinstance(value, dict), f"sources[{index}] must be an object")
        ticker = str(value.get("ticker", "")).strip().upper()
        source_name = str(value.get("source_name", "")).strip()
        source_kind = str(value.get("source_kind", "feed")).strip().casefold()
        allowed_value = value.get("allowed_hosts")
        require(ticker and source_name, f"sources[{index}] has missing required fields")
        require(ticker not in seen_tickers, f"duplicate official-source ticker: {ticker}")
        seen_tickers.add(ticker)
        require(source_kind in {"feed", "html_release_index"}, f"unsupported source kind: {source_kind}")
        require(isinstance(allowed_value, list) and allowed_value, f"sources[{index}].allowed_hosts must be a non-empty list")
        allowed_hosts = {str(host).strip().casefold() for host in allowed_value}
        require(all(allowed_hosts), f"sources[{index}] contains an empty allowed host")
        if source_kind == "feed":
            feed_url = str(value.get("feed_url", "")).strip()
            require(feed_url and host_is_allowed(feed_url, allowed_hosts), f"sources[{index}] feed URL is not allowlisted")
            feed_sources.append(
                {
                    "ticker": ticker,
                    "source_name": source_name,
                    "feed_url": feed_url,
                    "allowed_hosts": sorted(allowed_hosts),
                }
            )
        else:
            index_url = str(value.get("index_url", "")).strip()
            require(index_url and host_is_allowed(index_url, allowed_hosts), f"sources[{index}] index URL is not allowlisted")
            html_sources.append(
                {
                    "ticker": ticker,
                    "source_name": source_name,
                    "index_url": index_url,
                    "allowed_hosts": allowed_hosts,
                }
            )
    return feed_sources, html_sources


def collect_company_feeds_live(
    config: dict[str, Any],
    *,
    collected_at_utc: str,
    user_agent: str,
    lookback_days: int,
    fetcher: Callable[..., HttpResult] = fetch_bytes,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    require(bool(user_agent.strip()), "official company collection requires a user agent")
    require(1 <= lookback_days <= 30, "lookback_days must be between 1 and 30")
    feed_sources, html_sources = _split_sources(config)
    collected_at = feed_adapter.parse_collected_at(collected_at_utc)
    cutoff = collected_at - timedelta(days=lookback_days)

    records: list[dict[str, Any]] = []
    failures: list[str] = []
    request_count = 0
    html_index_pages_fetched = 0

    if feed_sources:
        feed_records, feed_metrics = feed_adapter.collect_company_feeds_live(
            {"schema_version": "1.0.0", "sources": feed_sources},
            collected_at_utc=collected_at_utc,
            user_agent=user_agent,
            lookback_days=lookback_days,
            fetcher=fetcher,
        )
        records.extend(feed_records)
        failures.extend(feed_metrics["failures"])
        request_count += int(feed_metrics["request_count"])

    limiter = RateLimiter(2.0)
    for source in html_sources:
        ticker = source["ticker"]
        try:
            result = fetcher(
                source["index_url"],
                allowed_hosts=source["allowed_hosts"],
                user_agent=user_agent,
                accept="text/html,application/xhtml+xml",
                rate_limiter=limiter,
            )
            request_count += result.request_count
            html_index_pages_fetched += 1
            for entry in parse_release_index(result.body, index_url=source["index_url"]):
                published_at = parse_release_index_timestamp(entry["published"])
                if published_at < cutoff or published_at > collected_at + timedelta(minutes=5):
                    continue
                link = entry["link"]
                require(host_is_allowed(link, source["allowed_hosts"]), "official release link left the allowlisted host")
                records.append(
                    build_public_record(
                        ticker=ticker,
                        published_at_utc=published_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
                        collected_at_utc=collected_at_utc,
                        source_type="company_release",
                        source_name=source["source_name"],
                        source_url=link,
                        headline=entry["title"],
                        summary=feed_adapter.clean_source_summary(entry["summary"]),
                        provider="official_company_source",
                        provider_article_id=entry["identifier"],
                        source_ticker=ticker,
                        filing_type=None,
                        event_identity=entry["identifier"],
                        primary_source=True,
                    )
                )
        except (CollectorError, KeyError, TypeError, ValueError):
            failures.append(f"official_company_source:{ticker}:collection_failed")

    seen_ids: set[tuple[str, str]] = set()
    for record in records:
        identity = (record["ticker"], record["provider_article_id"])
        require(identity not in seen_ids, f"duplicate official release ID: {identity[0]}:{identity[1]}")
        seen_ids.add(identity)
    records.sort(key=lambda row: (row["published_at_utc"], row["ticker"], row["provider_article_id"]))
    return records, {
        "schema_version": "1.0.0",
        "provider": "official_company_source",
        "request_count": request_count,
        "configured_source_count": len(feed_sources) + len(html_sources),
        "record_count": len(records),
        "failures": sorted(set(failures)),
        "article_pages_fetched": False,
        "html_index_pages_fetched": html_index_pages_fetched,
        "source_kind_counts": {"feed": len(feed_sources), "html_release_index": len(html_sources)},
    }
