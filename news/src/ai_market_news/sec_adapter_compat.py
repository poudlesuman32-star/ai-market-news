from __future__ import annotations

import re
from pathlib import PurePosixPath
from typing import Any, Callable
from urllib.parse import urlparse

from . import sec_adapter
from .collector_common import require
from .live_http import HttpResult, fetch_bytes

PRIMARY_DOCUMENT_MAX_BYTES = 2_000_000
FILING_INDEX_MAX_BYTES = 1_500_000
EXHIBIT_DOCUMENT_MAX_BYTES = 1_500_000
_EXCLUDED_EXHIBIT_PREFIXES = ("EX-101", "EX-104")
_HREF_PATTERN = re.compile(r"(?P<prefix>href\s*=\s*['\"])(?P<href>[^'\"]+)(?P<suffix>['\"])", re.IGNORECASE)
_SAFE_FILENAME = re.compile(r"[A-Za-z0-9._-]+")


def normalize_same_accession_index_links(body: bytes, *, index_url: str) -> bytes:
    """Convert SEC root-relative links to filenames only when they stay in the exact filing directory."""
    text = body.decode("utf-8", errors="replace")
    expected_parent = PurePosixPath(urlparse(index_url).path).parent

    def replace(match: re.Match[str]) -> str:
        href = match.group("href").strip()
        parsed = urlparse(href)
        if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment:
            return match.group(0)
        path = PurePosixPath(parsed.path)
        filename = path.name
        if (
            parsed.path.startswith("/")
            and path.parent == expected_parent
            and filename not in {"", ".", ".."}
            and _SAFE_FILENAME.fullmatch(filename)
        ):
            return f"{match.group('prefix')}{filename}{match.group('suffix')}"
        return match.group(0)

    return _HREF_PATTERN.sub(replace, text).encode("utf-8")


def parse_substantive_exhibit_documents(index_body: bytes, content_type: str) -> list[tuple[str, str]]:
    """Select bounded same-accession substantive exhibits while excluding XBRL metadata packages."""
    text = index_body.decode("utf-8", errors="replace")
    require("html" in content_type.casefold() or "<table" in text[:5000].casefold(), "SEC filing index is not HTML")
    parser = sec_adapter._FilingIndexParser()
    parser.feed(text)
    selected: list[tuple[str, str]] = []
    seen: set[str] = set()
    for cells, hrefs in parser.rows:
        exhibit_type = next(
            (cell.strip().upper() for cell in cells if cell.strip().upper().startswith("EX-")),
            "",
        )
        if not exhibit_type or exhibit_type.startswith(_EXCLUDED_EXHIBIT_PREFIXES):
            continue
        href = next((value for value in hrefs if value), None)
        if not href:
            continue
        filename = sec_adapter.safe_exhibit_filename(href)
        if filename in seen:
            continue
        seen.add(filename)
        selected.append((exhibit_type, filename))
        if len(selected) >= sec_adapter.MAX_EXHIBITS_PER_FILING:
            break
    return selected


def _reclassify_enrichment_metrics(metrics: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    skips = list(metrics.get("enrichment_skips", []))
    for value in metrics.get("enrichment_failures", []):
        text = str(value)
        if text.endswith(":filing_index:exhibit_not_found"):
            skips.append(text[: -len("exhibit_not_found")] + "no_substantive_exhibit_present")
        else:
            failures.append(text)
    return {
        **metrics,
        "enrichment_failures": sorted(set(failures)),
        "enrichment_skips": sorted(set(str(value) for value in skips)),
        "document_byte_limits": {
            "primary_document": PRIMARY_DOCUMENT_MAX_BYTES,
            "filing_index": FILING_INDEX_MAX_BYTES,
            "exhibit_document": EXHIBIT_DOCUMENT_MAX_BYTES,
        },
    }


def collect_sec_live(
    config: dict[str, Any],
    *,
    collected_at_utc: str,
    user_agent: str,
    lookback_days: int,
    fetcher: Callable[..., tuple[dict[str, Any], int]] = sec_adapter.fetch_json,
    document_fetcher: Callable[..., HttpResult] = fetch_bytes,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    selected_exhibit_filenames: set[str] = set()

    def tracked_exhibit_parser(body: bytes, content_type: str) -> list[tuple[str, str]]:
        selected = parse_substantive_exhibit_documents(body, content_type)
        selected_exhibit_filenames.update(filename for _, filename in selected)
        return selected

    def compatible_document_fetcher(url: str, **kwargs: Any) -> HttpResult:
        filename = PurePosixPath(urlparse(url).path).name
        if url.endswith("-index.html"):
            kwargs["max_bytes"] = FILING_INDEX_MAX_BYTES
        elif filename in selected_exhibit_filenames:
            kwargs["max_bytes"] = EXHIBIT_DOCUMENT_MAX_BYTES
        else:
            kwargs["max_bytes"] = PRIMARY_DOCUMENT_MAX_BYTES
        result = document_fetcher(url, **kwargs)
        if url.endswith("-index.html"):
            return HttpResult(
                body=normalize_same_accession_index_links(result.body, index_url=url),
                final_url=result.final_url,
                request_count=result.request_count,
                content_type=result.content_type,
            )
        return result

    original_parser = sec_adapter.parse_exhibit_documents
    original_maximum = sec_adapter.MAX_DOCUMENT_BYTES
    try:
        sec_adapter.parse_exhibit_documents = tracked_exhibit_parser
        sec_adapter.MAX_DOCUMENT_BYTES = PRIMARY_DOCUMENT_MAX_BYTES
        records, metrics = sec_adapter.collect_sec_live(
            config,
            collected_at_utc=collected_at_utc,
            user_agent=user_agent,
            lookback_days=lookback_days,
            fetcher=fetcher,
            document_fetcher=compatible_document_fetcher,
        )
    finally:
        sec_adapter.parse_exhibit_documents = original_parser
        sec_adapter.MAX_DOCUMENT_BYTES = original_maximum
    return records, _reclassify_enrichment_metrics(metrics)
