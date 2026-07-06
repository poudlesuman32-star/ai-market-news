import json
import unittest
import urllib.error
import urllib.parse
from datetime import date, datetime, timezone
from pathlib import Path

from scripts.provider_adapter import YahooChartAdapter, chart_url

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/provider/yahoo_chart_nvda.json"
START = date(2026, 5, 29)
END = date(2026, 7, 5)


class FakeResponse:
    status = 200

    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class ProviderAdapterTests(unittest.TestCase):
    def test_url_requests_regular_daily_adjusted_data(self):
        parsed = urllib.parse.urlparse(chart_url("NVDA", START, END))
        query = urllib.parse.parse_qs(parsed.query)
        self.assertEqual(parsed.netloc, "query1.finance.yahoo.com")
        self.assertEqual(query["interval"], ["1d"])
        self.assertEqual(query["events"], ["div,splits"])
        self.assertEqual(query["includeAdjustedClose"], ["true"])

    def test_temporary_failure_retries_and_records_attempt_count(self):
        payload = json.loads(FIXTURE.read_text())
        calls = []
        sleeps = []

        def opener(request, timeout):
            calls.append((request.full_url, timeout))
            if len(calls) == 1:
                raise urllib.error.URLError("temporary")
            return FakeResponse(payload)

        adapter = YahooChartAdapter(
            attempts=3,
            opener=opener,
            sleeper=sleeps.append,
            clock=lambda: datetime(2026, 7, 5, 23, 45, tzinfo=timezone.utc),
        )
        response = adapter.fetch("NVDA", START, END)
        self.assertEqual(response.attempt_count, 2)
        self.assertEqual(adapter.request_count, 2)
        self.assertEqual(sleeps, [1.0])
        self.assertEqual(response.retrieved_at_utc, "2026-07-05T23:45:00Z")


if __name__ == "__main__":
    unittest.main()
