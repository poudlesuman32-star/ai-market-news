from __future__ import annotations

from typing import Any, Callable

from . import company_source_compat
from .live_http import HttpResult, fetch_bytes

HTML_RELEASE_INDEX_MAX_BYTES = 4_000_000


def collect_company_feeds_live(
    config: dict[str, Any],
    *,
    collected_at_utc: str,
    user_agent: str,
    lookback_days: int,
    fetcher: Callable[..., HttpResult] = fetch_bytes,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Apply a dedicated bounded response limit to HTML release indexes.

    Feed collection keeps the shared HTTP default. Only allowlisted HTML release
    index requests receive the larger reviewed cap needed by current issuer pages.
    """

    def bounded_fetcher(url: str, **kwargs: Any) -> HttpResult:
        accept = str(kwargs.get("accept", "")).casefold()
        if "text/html" in accept:
            kwargs["max_bytes"] = HTML_RELEASE_INDEX_MAX_BYTES
        return fetcher(url, **kwargs)

    records, metrics = company_source_compat.collect_company_feeds_live(
        config,
        collected_at_utc=collected_at_utc,
        user_agent=user_agent,
        lookback_days=lookback_days,
        fetcher=bounded_fetcher,
    )
    return records, {
        **metrics,
        "html_release_index_max_bytes": HTML_RELEASE_INDEX_MAX_BYTES,
    }
