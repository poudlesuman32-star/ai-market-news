from __future__ import annotations

import unittest
from unittest.mock import patch

from ai_market_news.collector_common import CollectorError
from ai_market_news.live_http import RateLimiter, fetch_bytes


class FakeResponse:
    def __init__(self, *, body: bytes | None = None, timeout_on_read: bool = False) -> None:
        self.body = body or b""
        self.timeout_on_read = timeout_on_read
        self.headers = {"Content-Type": "application/xml"}

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, exc_type, exc, traceback) -> bool:
        return False

    def geturl(self) -> str:
        return "https://example.com/feed.xml"

    def read(self, size: int) -> bytes:
        if self.timeout_on_read:
            raise TimeoutError("simulated read timeout")
        return self.body[:size]


class LiveHttpTimeoutTests(unittest.TestCase):
    def test_read_timeout_is_retried_and_request_count_is_preserved(self) -> None:
        responses = [
            FakeResponse(timeout_on_read=True),
            FakeResponse(body=b"<rss><channel/></rss>"),
        ]

        def opener(request, timeout):
            return responses.pop(0)

        with patch("ai_market_news.live_http.time.sleep", return_value=None):
            result = fetch_bytes(
                "https://example.com/feed.xml",
                allowed_hosts={"example.com"},
                user_agent="PPI Test contact@example.com",
                accept="application/xml",
                rate_limiter=RateLimiter(10.0),
                retries=1,
                opener=opener,
            )

        self.assertEqual(result.body, b"<rss><channel/></rss>")
        self.assertEqual(result.request_count, 2)

    def test_exhausted_read_timeouts_become_collector_error(self) -> None:
        def opener(request, timeout):
            return FakeResponse(timeout_on_read=True)

        with patch("ai_market_news.live_http.time.sleep", return_value=None):
            with self.assertRaisesRegex(CollectorError, "network timeout or transport error"):
                fetch_bytes(
                    "https://example.com/feed.xml",
                    allowed_hosts={"example.com"},
                    user_agent="PPI Test contact@example.com",
                    accept="application/xml",
                    rate_limiter=RateLimiter(10.0),
                    retries=1,
                    opener=opener,
                )


if __name__ == "__main__":
    unittest.main()
