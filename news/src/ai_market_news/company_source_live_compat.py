from __future__ import annotations

from typing import Any, Callable
from urllib.parse import urlparse

from . import company_source_compat
from .collector_common import CollectorError, require
from .company_feed_adapter import parse_collected_at
from .live_http import HttpResult, fetch_bytes
from .micron_newsroom_adapter import parse_micron_newsroom_index

HTML_RELEASE_INDEX_MAX_BYTES = 4_000_000
_MICRON_NEWSROOM_PATH = "/about/press/news"


def _parse_compatible_release_index(body: bytes, *, index_url: str) -> list[dict[str, str]]:
    parsed = urlparse(index_url)
    if (parsed.hostname or "").casefold() == "www.micron.com" and parsed.path.rstrip("/") == _MICRON_NEWSROOM_PATH:
        return parse_micron_newsroom_index(body, index_url=index_url)
    return company_source_compat.parse_release_index(body, index_url=index_url)


def _activation_at(source: dict[str, Any], *, index: int):
    value = str(source.get("activation_at_utc", "")).strip()
    if not value:
        return None
    try:
        return parse_collected_at(value)
    except CollectorError as exc:
        raise CollectorError(f"sources[{index}].activation_at_utc is invalid") from exc


def collect_company_feeds_live(
    config: dict[str, Any],
    *,
    collected_at_utc: str,
    user_agent: str,
    lookback_days: int,
    fetcher: Callable[..., HttpResult] = fetch_bytes,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Apply reviewed compatibility rules and prospective activation gates to official sources."""

    require(config.get("schema_version") == "1.0.0", "unsupported official-source config schema")
    sources = config.get("sources")
    require(isinstance(sources, list) and sources, "official-source config must contain sources")

    def bounded_fetcher(url: str, **kwargs: Any) -> HttpResult:
        accept = str(kwargs.get("accept", "")).casefold()
        if "text/html" in accept:
            kwargs["max_bytes"] = HTML_RELEASE_INDEX_MAX_BYTES
        return fetcher(url, **kwargs)

    records: list[dict[str, Any]] = []
    failures: list[str] = []
    request_count = 0
    html_index_pages_fetched = 0
    source_kind_counts = {"feed": 0, "html_release_index": 0}
    activation_filtered_record_count = 0

    original_parser = company_source_compat.parse_release_index
    try:
        company_source_compat.parse_release_index = _parse_compatible_release_index
        for index, source in enumerate(sources):
            require(isinstance(source, dict), f"sources[{index}] must be an object")
            activation = _activation_at(source, index=index)
            source_config = {"schema_version": "1.0.0", "sources": [source]}
            source_records, source_metrics = company_source_compat.collect_company_feeds_live(
                source_config,
                collected_at_utc=collected_at_utc,
                user_agent=user_agent,
                lookback_days=lookback_days,
                fetcher=bounded_fetcher,
            )
            request_count += int(source_metrics["request_count"])
            html_index_pages_fetched += int(source_metrics.get("html_index_pages_fetched", 0))
            failures.extend(str(value) for value in source_metrics.get("failures", []))
            for kind, count in source_metrics.get("source_kind_counts", {}).items():
                source_kind_counts[str(kind)] = source_kind_counts.get(str(kind), 0) + int(count)
            for record in source_records:
                if activation is not None and parse_collected_at(record["published_at_utc"]) < activation:
                    activation_filtered_record_count += 1
                    continue
                records.append(record)
    finally:
        company_source_compat.parse_release_index = original_parser

    deduplicated: list[dict[str, Any]] = []
    id_to_url: dict[tuple[str, str], str] = {}
    seen_urls: set[tuple[str, str]] = set()
    overlap_deduplicated_record_count = 0
    for record in records:
        identity = (str(record["ticker"]), str(record["provider_article_id"]))
        url_identity = (str(record["ticker"]), str(record["source_url"]))
        previous_url = id_to_url.get(identity)
        if previous_url is not None:
            require(previous_url == url_identity[1], f"conflicting official release ID: {identity[0]}:{identity[1]}")
            overlap_deduplicated_record_count += 1
            continue
        if url_identity in seen_urls:
            overlap_deduplicated_record_count += 1
            continue
        id_to_url[identity] = url_identity[1]
        seen_urls.add(url_identity)
        deduplicated.append(record)

    deduplicated.sort(key=lambda row: (row["published_at_utc"], row["ticker"], row["provider_article_id"]))
    return deduplicated, {
        "schema_version": "1.0.0",
        "provider": "official_company_source",
        "request_count": request_count,
        "configured_source_count": len(sources),
        "record_count": len(deduplicated),
        "failures": sorted(set(failures)),
        "article_pages_fetched": False,
        "html_index_pages_fetched": html_index_pages_fetched,
        "source_kind_counts": source_kind_counts,
        "activation_filtered_record_count": activation_filtered_record_count,
        "overlap_deduplicated_record_count": overlap_deduplicated_record_count,
        "html_release_index_max_bytes": HTML_RELEASE_INDEX_MAX_BYTES,
    }
