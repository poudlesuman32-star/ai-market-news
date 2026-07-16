from __future__ import annotations

import hashlib
import re
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import PurePosixPath
from typing import Any, Callable
from urllib.parse import urlparse

from .collector_common import CollectorError, build_public_record, require
from .live_http import HttpResult, RateLimiter, fetch_bytes, fetch_json

SEC_HOSTS = {"sec.gov"}
SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
SUBSTANTIVE_FORMS = {"8-K", "10-K", "10-Q", "6-K"}
EXHIBIT_TYPE_PREFIX = "EX-99"
MAX_DOCUMENT_BYTES = 1_500_000
MAX_PRIMARY_EXCERPT_CHARS = 1_200
MAX_EXHIBIT_EXCERPT_CHARS = 1_600
MAX_EXHIBITS_PER_FILING = 2
MAX_PUBLIC_SUMMARY_CHARS = 3_900


class UnsafeExhibitLinkError(CollectorError):
    pass


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


class _FilingIndexParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._in_row = False
        self._in_cell = False
        self._cells: list[str] = []
        self._cell_parts: list[str] = []
        self._cell_href: str | None = None
        self.rows: list[tuple[list[str], list[str | None]]] = []
        self._hrefs: list[str | None] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        lowered = tag.casefold()
        if lowered == "tr":
            self._in_row = True
            self._cells = []
            self._hrefs = []
        elif self._in_row and lowered in {"td", "th"}:
            self._in_cell = True
            self._cell_parts = []
            self._cell_href = None
        elif self._in_cell and lowered == "a":
            self._cell_href = dict(attrs).get("href")

    def handle_endtag(self, tag: str) -> None:
        lowered = tag.casefold()
        if self._in_cell and lowered in {"td", "th"}:
            self._cells.append(" ".join(" ".join(self._cell_parts).split()))
            self._hrefs.append(self._cell_href)
            self._in_cell = False
        elif self._in_row and lowered == "tr":
            if self._cells:
                self.rows.append((list(self._cells), list(self._hrefs)))
            self._in_row = False

    def handle_data(self, data: str) -> None:
        if self._in_cell and data.strip():
            self._cell_parts.append(data)


def extract_document_text(body: bytes, content_type: str) -> str:
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


def bounded_document_excerpt(text: str, maximum: int) -> str:
    normalized = " ".join(text.split())
    require(bool(normalized), "SEC document contains no readable text")
    require(maximum > 0, "SEC excerpt maximum must be positive")
    if len(normalized) <= maximum:
        return normalized
    clipped = normalized[:maximum]
    boundary = clipped.rfind(" ")
    if boundary >= maximum // 2:
        clipped = clipped[:boundary]
    return clipped.rstrip() + "…"


def bounded_public_summary(parts: list[str]) -> str:
    value = " ".join(parts)
    if len(value) <= MAX_PUBLIC_SUMMARY_CHARS:
        return value
    clipped = value[:MAX_PUBLIC_SUMMARY_CHARS]
    boundary = clipped.rfind(" ")
    if boundary >= MAX_PUBLIC_SUMMARY_CHARS // 2:
        clipped = clipped[:boundary]
    return clipped.rstrip() + "…"


def safe_exhibit_filename(href: str) -> str:
    parsed = urlparse(str(href).strip())
    if parsed.scheme or parsed.netloc:
        raise UnsafeExhibitLinkError("SEC exhibit link must be relative")
    path = PurePosixPath(parsed.path)
    if len(path.parts) != 1:
        raise UnsafeExhibitLinkError("SEC exhibit link must reference one same-accession file")
    filename = path.name
    if not filename or filename in {".", ".."}:
        raise UnsafeExhibitLinkError("SEC exhibit filename is invalid")
    if re.fullmatch(r"[A-Za-z0-9._-]+", filename) is None:
        raise UnsafeExhibitLinkError("SEC exhibit filename is unsafe")
    return filename


def parse_exhibit_documents(index_body: bytes, content_type: str) -> list[tuple[str, str]]:
    text = index_body.decode("utf-8", errors="replace")
    require("html" in content_type.casefold() or "<table" in text[:5000].casefold(), "SEC filing index is not HTML")
    parser = _FilingIndexParser()
    parser.feed(text)
    selected: list[tuple[str, str]] = []
    seen: set[str] = set()
    for cells, hrefs in parser.rows:
        exhibit_type = next(
            (cell.strip().upper() for cell in cells if cell.strip().upper().startswith(EXHIBIT_TYPE_PREFIX)),
            "",
        )
        if not exhibit_type:
            continue
        href = next((value for value in hrefs if value), None)
        if not href:
            continue
        filename = safe_exhibit_filename(href)
        if filename in seen:
            continue
        seen.add(filename)
        selected.append((exhibit_type, filename))
        if len(selected) >= MAX_EXHIBITS_PER_FILING:
            break
    return selected


def classify_enrichment_error(error: Exception) -> str:
    message = str(error).casefold()
    if "exceeds" in message and "bytes" in message:
        return "response_too_large"
    match = re.search(r"http\s+(\d{3})", message)
    if match:
        return f"http_{match.group(1)}"
    if "timeout" in message or "transport" in message or "retries" in message:
        return "transport_error"
    if "no readable text" in message:
        return "unreadable_document"
    if "not html" in message:
        return "invalid_index_html"
    return "processing_error"


def enrichment_failure(ticker: str, accession: str, stage: str, error: Exception | str) -> str:
    reason = error if isinstance(error, str) else classify_enrichment_error(error)
    return f"sec_edgar:{ticker}:{accession}:{stage}:{reason}"


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
    enrichment_failures: list[str] = []
    seen_accessions: set[str] = set()
    request_count = 0
    primary_hashes: dict[str, str] = {}
    exhibit_hashes: dict[str, dict[str, str]] = {}
    primary_fetch_count = 0
    exhibit_fetch_count = 0

    for company in companies:
        ticker = company["ticker"]
        url = SEC_SUBMISSIONS_URL.format(cik=company["cik"])
        try:
            payload, attempts = fetcher(url, allowed_hosts=SEC_HOSTS, user_agent=user_agent, rate_limiter=limiter)
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
                filing_root = f"https://www.sec.gov/Archives/edgar/data/{cik_path}/{accession_path}"
                source_url = f"{filing_root}/{primary_document}"
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
                    primary_ok = False
                    try:
                        document = document_fetcher(
                            source_url,
                            allowed_hosts=SEC_HOSTS,
                            user_agent=user_agent,
                            accept="text/html,application/xhtml+xml,text/plain,application/xml;q=0.9,*/*;q=0.1",
                            rate_limiter=limiter,
                            max_bytes=MAX_DOCUMENT_BYTES,
                        )
                        request_count += document.request_count
                        primary_fetch_count += 1
                        primary_hashes[accession] = hashlib.sha256(document.body).hexdigest()
                        primary_excerpt = bounded_document_excerpt(
                            extract_document_text(document.body, document.content_type), MAX_PRIMARY_EXCERPT_CHARS
                        )
                        summary_parts.append(f"Verified primary-document excerpt: {primary_excerpt}")
                        primary_ok = True
                    except (CollectorError, KeyError, TypeError, ValueError) as exc:
                        enrichment_failures.append(enrichment_failure(ticker, accession, "primary_document", exc))

                    if primary_ok:
                        selected_exhibits: list[tuple[str, str]] = []
                        try:
                            index_url = f"{filing_root}/{accession}-index.html"
                            index_document = document_fetcher(
                                index_url,
                                allowed_hosts=SEC_HOSTS,
                                user_agent=user_agent,
                                accept="text/html,application/xhtml+xml",
                                rate_limiter=limiter,
                                max_bytes=MAX_DOCUMENT_BYTES,
                            )
                            request_count += index_document.request_count
                            selected_exhibits = parse_exhibit_documents(index_document.body, index_document.content_type)
                            if not selected_exhibits:
                                enrichment_failures.append(
                                    enrichment_failure(ticker, accession, "filing_index", "exhibit_not_found")
                                )
                        except UnsafeExhibitLinkError:
                            raise
                        except (CollectorError, KeyError, TypeError, ValueError) as exc:
                            enrichment_failures.append(enrichment_failure(ticker, accession, "filing_index", exc))

                        if selected_exhibits:
                            exhibit_hashes[accession] = {}
                        for exhibit_type, filename in selected_exhibits:
                            try:
                                exhibit_url = f"{filing_root}/{filename}"
                                exhibit = document_fetcher(
                                    exhibit_url,
                                    allowed_hosts=SEC_HOSTS,
                                    user_agent=user_agent,
                                    accept="text/html,application/xhtml+xml,text/plain,application/xml;q=0.9,*/*;q=0.1",
                                    rate_limiter=limiter,
                                    max_bytes=MAX_DOCUMENT_BYTES,
                                )
                                request_count += exhibit.request_count
                                exhibit_fetch_count += 1
                                exhibit_hashes[accession][filename] = hashlib.sha256(exhibit.body).hexdigest()
                                exhibit_excerpt = bounded_document_excerpt(
                                    extract_document_text(exhibit.body, exhibit.content_type), MAX_EXHIBIT_EXCERPT_CHARS
                                )
                                summary_parts.append(
                                    f"Verified {exhibit_type} exhibit excerpt ({filename}): {exhibit_excerpt}"
                                )
                            except (CollectorError, KeyError, TypeError, ValueError) as exc:
                                enrichment_failures.append(enrichment_failure(ticker, accession, f"exhibit:{filename}", exc))

                records.append(
                    build_public_record(
                        ticker=ticker,
                        published_at_utc=published,
                        collected_at_utc=collected_at_utc,
                        source_type="sec_filing",
                        source_name=f"{company['company_name']} SEC filing",
                        source_url=source_url,
                        headline=headline,
                        summary=bounded_public_summary(summary_parts),
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
        "enrichment_failures": sorted(set(enrichment_failures)),
        "full_document_content_fetched": primary_fetch_count > 0,
        "primary_document_fetch_count": primary_fetch_count,
        "primary_document_sha256": dict(sorted(primary_hashes.items())),
        "exhibit_document_fetch_count": exhibit_fetch_count,
        "exhibit_document_sha256": {
            accession: dict(sorted(values.items())) for accession, values in sorted(exhibit_hashes.items())
        },
    }
