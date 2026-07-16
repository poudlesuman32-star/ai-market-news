from __future__ import annotations

import hashlib
import re
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from typing import Any, Callable

from .collector_common import CollectorError, build_public_record, require
from .live_http import HttpResult, RateLimiter, fetch_bytes, fetch_json

SEC_HOSTS = {"sec.gov"}
SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
SUBSTANTIVE_FORMS = {"8-K", "10-K", "10-Q", "6-K"}
MAX_DOCUMENT_BYTES = 1_500_000
MAX_DOCUMENT_EXCERPT_CHARS = 2_400


class _VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._hidden_depth = 0
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() in {"script", "style", "noscript"}:
            self._hidden_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() in {"script", "style", "noscript"} and self._hidden_depth:
            self._hidden_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._hidden_depth == 0 and data.strip():
            self._parts.append(data)

    def text(self) -> str:
        return " ".join(self._parts)


def extract_primary_document_text(body: bytes, content_type: str) -> str:
    try:
        decoded = body.decode("utf-8")
    except UnicodeDecodeError:
        decoded = body.decode("utf-8", errors="replace")
    lowered = content_type.casefold()
    if "html" in lowered or "xml" in lowered or "<html" in decoded[:500].casefold():
        parser = _VisibleTextParser()
        parser.feed(decoded)
        decoded = parser.text()
    return " ".join(decoded.split())


def bounded_document_excerpt(text: str) -> str:
    normalized = " ".join(text.split())
    require(bool(normalized), "SEC primary document contains no readable text")
    if len(normalized) <= MAX_DOCUMENT_EXCERPT_CHARS:
        return normalized
    clipped = normalized[:MAX_DOCUMENT_EXCERPT_CHARS]
    boundary = clipped.rfind(" ")
    if boundary >= MAX_DOCUMENT_EXCERPT_CHARS // 2:
        clipped = clipped[:boundary]
    return clipped.rstrip() + "…"


def parse_utc(value: str) -> datetime:
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise CollectorError(f"invalid UTC timestamp: {value!r}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def sec_publication_timestamp(acceptance: object, filing_date: object) -> str:
    acceptance_text = str(acceptance or "").strip()
    if acceptance_text:
        return parse_utc(acceptance_text).strftime("%Y-%m-%dT%H:%M:%SZ")
    filing_text = str(filing_date or "").strip()
    try:
        parsed = datetime.strptime(filing_text, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise CollectorError("SEC filing is missing a valid acceptance or filing timestamp") from exc
    return parsed.strftime("%Y-%m-%dT%H:%M:%SZ")


def recent_value(recent: dict[str, Any], name: str, index: int) -> object:
    values = recent.get(name, [])
    if not isinstance(values, list) or index >= len(values):
        return ""
    return values[index]


def validate_config(config: dict[str, Any]) -> tuple[set[str], list[dict[str, str]]]:
    require(config.get("schema_version") == "1.0.0", "unsupported SEC live-source config schema")
    forms_value = config.get("forms")
    companies_value = config.get("companies")
    require(isinstance(forms_value, list) and forms_value, "SEC config forms must be a non-empty list")
    require(isinstance(companies_value, list) and companies_value, "SEC config companies must be a non-empty list")
    forms = {str(value).strip().upper() for value in forms_value}
    require(all(forms), "SEC config contains an empty form")

    companies: list[dict[str, str]] = []
    seen_tickers: set[str] = set()
    seen_ciks: set[str] = set()
    for index, value in enumerate(companies_value):
        require(isinstance(value, dict), f"companies[{index}] must be an object")
        ticker = str(value.get("ticker", "")).strip().upper()
        cik = str(value.get("cik", "")).strip().zfill(10)
        company_name = str(value.get("company_name", "")).strip()
        require(bool(ticker and company_name), f"companies[{index}] ticker and company_name are required")
        require(cik.isdigit() and len(cik) == 10, f"companies[{index}] CIK must contain ten digits")
        require(ticker not in seen_tickers, f"duplicate SEC ticker in config: {ticker}")
        require(cik not in seen_ciks, f"duplicate SEC CIK in config: {cik}")
        seen_tickers.add(ticker)
        seen_ciks.add(cik)
        companies.append({"ticker": ticker, "cik": cik, "company_name": company_name})
    return forms, companies


def collect_sec_live(
    config: dict[str, Any],
    *,
    collected_at_utc: str,
    user_agent: str,
    lookback_days: int,
    fetcher: Callable[..., tuple[dict[str, Any], int]] = fetch_json,
    document_fetcher: Callable[..., HttpResult] = fetch_bytes,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    require(bool(user_agent.strip()), "SEC live collection requires a declared user agent")
    require("@" in user_agent, "SEC user agent must include a contact email")
    require(1 <= lookback_days <= 30, "lookback_days must be between 1 and 30")
    forms, companies = validate_config(config)
    collected_at = parse_utc(collected_at_utc)
    cutoff = collected_at - timedelta(days=lookback_days)
    limiter = RateLimiter(8.0)

    records: list[dict[str, Any]] = []
    failures: list[str] = []
    seen_accessions: set[str] = set()
    request_count = 0
    document_hashes: dict[str, str] = {}
    document_fetch_count = 0

    for company in companies:
        ticker = company["ticker"]
        url = SEC_SUBMISSIONS_URL.format(cik=company["cik"])
        try:
            payload, attempts = fetcher(
                url,
                allowed_hosts=SEC_HOSTS,
                user_agent=user_agent,
                rate_limiter=limiter,
            )
            request_count += attempts
            filings = payload.get("filings")
            require(isinstance(filings, dict), "SEC submissions response is missing filings")
            recent = filings.get("recent")
            require(isinstance(recent, dict), "SEC submissions response is missing filings.recent")
            accessions = recent.get("accessionNumber")
            require(isinstance(accessions, list), "SEC submissions response is missing accession numbers")

            for index, accession_value in enumerate(accessions):
                accession = str(accession_value).strip()
                form = str(recent_value(recent, "form", index)).strip().upper()
                if not accession or form not in forms:
                    continue
                published = sec_publication_timestamp(
                    recent_value(recent, "acceptanceDateTime", index),
                    recent_value(recent, "filingDate", index),
                )
                published_at = parse_utc(published)
                if published_at < cutoff or published_at > collected_at + timedelta(minutes=5):
                    continue
                require(accession not in seen_accessions, f"duplicate SEC accession number: {accession}")
                seen_accessions.add(accession)

                primary_document = str(recent_value(recent, "primaryDocument", index)).strip()
                require(bool(primary_document), "SEC filing is missing primaryDocument")
                accession_path = accession.replace("-", "")
                cik_path = str(int(company["cik"]))
                source_url = (
                    f"https://www.sec.gov/Archives/edgar/data/{cik_path}/"
                    f"{accession_path}/{primary_document}"
                )
                description = str(recent_value(recent, "primaryDocDescription", index)).strip()
                items = str(recent_value(recent, "items", index)).strip()
                report_date = str(recent_value(recent, "reportDate", index)).strip()
                headline = f"{form}: {description or 'SEC filing'}"
                summary_parts = [f"{company['company_name']} filed form {form} with the SEC."]
                if items:
                    summary_parts.append(f"Reported items: {items}.")
                if report_date:
                    summary_parts.append(f"Report date: {report_date}.")

                if form in SUBSTANTIVE_FORMS:
                    document = document_fetcher(
                        source_url,
                        allowed_hosts=SEC_HOSTS,
                        user_agent=user_agent,
                        accept="text/html,application/xhtml+xml,text/plain,application/xml;q=0.9,*/*;q=0.1",
                        rate_limiter=limiter,
                        max_bytes=MAX_DOCUMENT_BYTES,
                    )
                    request_count += document.request_count
                    document_fetch_count += 1
                    document_hashes[accession] = hashlib.sha256(document.body).hexdigest()
                    excerpt = bounded_document_excerpt(
                        extract_primary_document_text(document.body, document.content_type)
                    )
                    summary_parts.append(f"Verified primary-document excerpt: {excerpt}")

                records.append(
                    build_public_record(
                        ticker=ticker,
                        published_at_utc=published,
                        collected_at_utc=collected_at_utc,
                        source_type="sec_filing",
                        source_name=f"{company['company_name']} SEC filing",
                        source_url=source_url,
                        headline=headline,
                        summary=" ".join(summary_parts),
                        provider="sec_edgar",
                        provider_article_id=accession,
                        source_ticker=ticker,
                        filing_type=form,
                        event_identity=accession,
                        primary_source=True,
                    )
                )
        except (CollectorError, KeyError, TypeError, ValueError):
            failures.append(f"sec_edgar:{ticker}:collection_failed")

    records.sort(key=lambda row: (row["published_at_utc"], row["ticker"], row["provider_article_id"]))
    return records, {
        "schema_version": "1.0.0",
        "provider": "sec_edgar",
        "request_count": request_count,
        "configured_source_count": len(companies),
        "record_count": len(records),
        "failures": sorted(set(failures)),
        "full_document_content_fetched": document_fetch_count > 0,
        "primary_document_fetch_count": document_fetch_count,
        "primary_document_sha256": dict(sorted(document_hashes.items())),
    }
