from __future__ import annotations

import gzip
import json
import time
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from .collector_common import CollectorError, require

RETRYABLE_STATUS = {429, 500, 502, 503, 504}
DEFAULT_MAX_BYTES = 2_000_000


@dataclass(frozen=True)
class HttpResult:
    body: bytes
    final_url: str
    request_count: int
    content_type: str


class RateLimiter:
    def __init__(self, requests_per_second: float) -> None:
        require(0 < requests_per_second <= 10, "requests_per_second must be between 0 and 10")
        self._minimum_interval = 1.0 / requests_per_second
        self._last_request: float | None = None

    def wait(self) -> None:
        now = time.monotonic()
        if self._last_request is not None:
            remaining = self._minimum_interval - (now - self._last_request)
            if remaining > 0:
                time.sleep(remaining)
        self._last_request = time.monotonic()


def host_is_allowed(url: str, allowed_hosts: set[str]) -> bool:
    parsed = urlparse(url)
    host = (parsed.hostname or "").casefold()
    return parsed.scheme == "https" and any(host == item or host.endswith("." + item) for item in allowed_hosts)


def validate_request_url(url: str, allowed_hosts: set[str]) -> None:
    parsed = urlparse(url)
    require(parsed.scheme == "https", f"live URL must use https: {url!r}")
    require(parsed.username is None and parsed.password is None, "URL credentials are forbidden")
    require(host_is_allowed(url, allowed_hosts), f"live URL host is not allowlisted: {url!r}")


def retry_delay(error: HTTPError, attempt: int) -> float:
    retry_after = error.headers.get("Retry-After") if error.headers else None
    if retry_after:
        try:
            return min(float(retry_after), 30.0)
        except ValueError:
            try:
                target = parsedate_to_datetime(retry_after).timestamp()
                return max(0.0, min(target - time.time(), 30.0))
            except (TypeError, ValueError, OverflowError):
                pass
    return min(2.0 ** attempt, 8.0)


def fetch_bytes(
    url: str,
    *,
    allowed_hosts: set[str],
    user_agent: str,
    accept: str,
    rate_limiter: RateLimiter,
    timeout_seconds: float = 20.0,
    max_bytes: int = DEFAULT_MAX_BYTES,
    retries: int = 3,
    opener: Callable[..., Any] = urlopen,
) -> HttpResult:
    validate_request_url(url, allowed_hosts)
    require(bool(user_agent.strip()), "a declared user agent is required")
    require(max_bytes > 0, "max_bytes must be positive")
    require(0 <= retries <= 5, "retries must be between 0 and 5")

    request_count = 0
    for attempt in range(retries + 1):
        rate_limiter.wait()
        request_count += 1
        request = Request(
            url,
            headers={
                "User-Agent": user_agent,
                "Accept": accept,
                "Accept-Encoding": "gzip",
            },
            method="GET",
        )
        try:
            with opener(request, timeout=timeout_seconds) as response:
                final_url = response.geturl()
                require(host_is_allowed(final_url, allowed_hosts), "redirected response host is not allowlisted")
                body = response.read(max_bytes + 1)
                require(len(body) <= max_bytes, f"response exceeds {max_bytes} bytes")
                if response.headers.get("Content-Encoding", "").casefold() == "gzip":
                    body = gzip.decompress(body)
                    require(len(body) <= max_bytes, f"decompressed response exceeds {max_bytes} bytes")
                return HttpResult(
                    body=body,
                    final_url=final_url,
                    request_count=request_count,
                    content_type=response.headers.get("Content-Type", ""),
                )
        except HTTPError as exc:
            if exc.code not in RETRYABLE_STATUS or attempt == retries:
                raise CollectorError(f"HTTP {exc.code} while fetching allowlisted primary source") from exc
            time.sleep(retry_delay(exc, attempt))
        except URLError as exc:
            if attempt == retries:
                raise CollectorError("network error while fetching allowlisted primary source") from exc
            time.sleep(min(2.0 ** attempt, 8.0))

    raise CollectorError("primary-source request exhausted retries")


def fetch_json(
    url: str,
    *,
    allowed_hosts: set[str],
    user_agent: str,
    rate_limiter: RateLimiter,
) -> tuple[dict[str, Any], int]:
    result = fetch_bytes(
        url,
        allowed_hosts=allowed_hosts,
        user_agent=user_agent,
        accept="application/json",
        rate_limiter=rate_limiter,
    )
    try:
        value = json.loads(result.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CollectorError("primary-source response is not valid UTF-8 JSON") from exc
    require(isinstance(value, dict), "primary-source JSON response must be an object")
    return value, result.request_count
