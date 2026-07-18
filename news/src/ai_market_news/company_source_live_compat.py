from __future__ import annotations

from typing import Any, Callable
from urllib.parse import urlparse

from . import company_source_compat
from .live_http import HttpResult, fetch_bytes
from .micron_newsroom_adapter import parse_micron_newsroom_index

HTML_RELEASE_INDEX_MAX_BYTES = 4_000_000
_MICRON_NEWSROOM_PATH = "/about/press/news"


def _parse_compatible_release_index(body: bytes, *, index_url: str) -> list[dict[str, str]]:
    parsed = urlparse(index_url)
    if (parsed.hostname or "").casefold() == "www.micron.com" and parsed.path.rstrip("/") == _MICRON_NEWSROOM_PATH:
        return parse_micron_newsroom_index(body, index_url=index_url)
    return company_source_compat.parse_release_index(body, index_url=index_url)


def collect_company_feeds_live(
    config: dict[str, Any],
    *,
    collected_at_utc: str,
    user_agent: str,
    lookback_days: int,
    fetcher: Callable[..., HttpResult] = fetch_bytes,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Apply reviewed compatibility rules to allowlisted HTML release indexes."""

    def bounded_fetcher(url: str, **kwargs: Any) -> HttpResult:
        accept = str(kwargs.get("accept", "")).casefold()
        if "text/html" in accept:
            kwargs["max_bytes"] = HTML_RELEASE_INDEX_MAX_BYTES
        return fetcher(url, **kwargs)

    original_parser = company_source_compat.parse_release_index
    try:
        company_source_compat.parse_release_index = _parse_compatible_release_index
        records, metrics = company_source_compat.collect_company_feeds_live(
            config,
            collected_at_utc=collected_at_utc,
            user_agent=user_agent,
            lookback_days=lookback_days,
            fetcher=bounded_fetcher,
        )
    finally:
        company_source_compat.parse_release_index = original_parser

    return records, {
        **metrics,
        "html_release_index_max_bytes": HTML_RELEASE_INDEX_MAX_BYTES,
    }
