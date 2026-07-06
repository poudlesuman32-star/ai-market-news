#!/usr/bin/env python3
"""Credential-free provider adapter for public daily market bars."""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, time as dt_time, timedelta, timezone
from typing import Any, Callable

from scripts.contract_common import require

PROVIDER_NAME = "Yahoo Finance chart API"
PROVIDER_HOST = "query1.finance.yahoo.com"
USER_AGENT = "ai-market-news-public-collector/1.0 (+https://github.com/poudlesuman32-star/ai-market-news)"


def epoch_seconds(day: date) -> int:
    return int(datetime.combine(day, dt_time.min, tzinfo=timezone.utc).timestamp())


def chart_url(symbol: str, start_date: date, end_date: date) -> str:
    require(start_date <= end_date, "provider request start date exceeds end date")
    params = urllib.parse.urlencode(
        {
            "period1": epoch_seconds(start_date - timedelta(days=1)),
            "period2": epoch_seconds(end_date + timedelta(days=2)),
            "interval": "1d",
            "events": "div,splits",
            "includeAdjustedClose": "true",
        }
    )
    return f"https://{PROVIDER_HOST}/v8/finance/chart/{urllib.parse.quote(symbol, safe='')}?{params}"


@dataclass(frozen=True)
class ProviderResponse:
    payload: dict[str, Any]
    request_url: str
    retrieved_at_utc: str
    attempt_count: int


class YahooChartAdapter:
    """Small retrying adapter around Yahoo's public chart endpoint."""

    provider_name = PROVIDER_NAME
    provider_host = PROVIDER_HOST

    def __init__(
        self,
        *,
        attempts: int = 4,
        timeout_seconds: int = 30,
        opener: Callable[..., Any] = urllib.request.urlopen,
        sleeper: Callable[[float], None] = time.sleep,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        require(attempts >= 1, "provider attempts must be positive")
        require(timeout_seconds >= 1, "provider timeout must be positive")
        self.attempts = attempts
        self.timeout_seconds = timeout_seconds
        self.opener = opener
        self.sleeper = sleeper
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.request_count = 0

    def fetch(self, symbol: str, start_date: date, end_date: date) -> ProviderResponse:
        url = chart_url(symbol, start_date, end_date)
        last_error: Exception | None = None
        for attempt in range(1, self.attempts + 1):
            self.request_count += 1
            request = urllib.request.Request(
                url,
                headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            )
            try:
                with self.opener(request, timeout=self.timeout_seconds) as response:
                    status = getattr(response, "status", 200)
                    require(status == 200, f"provider returned HTTP {status}")
                    payload = json.loads(response.read().decode("utf-8"))
                    require(isinstance(payload, dict), "provider response is not a JSON object")
                    retrieved = self.clock().astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
                    return ProviderResponse(payload, url, retrieved, attempt)
            except (
                OSError,
                TimeoutError,
                urllib.error.URLError,
                json.JSONDecodeError,
                UnicodeDecodeError,
                ValueError,
            ) as exc:
                last_error = exc
                if attempt < self.attempts:
                    self.sleeper(float(2 ** (attempt - 1)))
        raise ValueError(f"provider request failed for {symbol} after {self.attempts} attempts: {last_error}")
