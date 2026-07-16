from __future__ import annotations

import re
from pathlib import PurePosixPath
from typing import Any, Callable
from urllib.parse import urlparse

from . import sec_adapter
from .live_http import HttpResult, fetch_bytes

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


def collect_sec_live(
    config: dict[str, Any],
    *,
    collected_at_utc: str,
    user_agent: str,
    lookback_days: int,
    fetcher: Callable[..., tuple[dict[str, Any], int]] = sec_adapter.fetch_json,
    document_fetcher: Callable[..., HttpResult] = fetch_bytes,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    def compatible_document_fetcher(url: str, **kwargs: Any) -> HttpResult:
        result = document_fetcher(url, **kwargs)
        if url.endswith("-index.html"):
            return HttpResult(
                body=normalize_same_accession_index_links(result.body, index_url=url),
                final_url=result.final_url,
                request_count=result.request_count,
                content_type=result.content_type,
            )
        return result

    return sec_adapter.collect_sec_live(
        config,
        collected_at_utc=collected_at_utc,
        user_agent=user_agent,
        lookback_days=lookback_days,
        fetcher=fetcher,
        document_fetcher=compatible_document_fetcher,
    )
