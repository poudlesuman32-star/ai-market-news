from __future__ import annotations

import unittest

from ai_market_news.collector_common import CollectorError
from ai_market_news.company_source_compat import parse_release_index
from ai_market_news.company_source_live_compat import HTML_RELEASE_INDEX_MAX_BYTES, collect_company_feeds_live
from ai_market_news.live_http import HttpResult
from ai_market_news.micron_newsroom_adapter import parse_micron_newsroom_index


HISTORICAL_INDEX_URL = "https://investors.micron.com/latest-news-english"
HISTORICAL_INDEX_HTML = b"""
<html><body>
  <div class='views-row'>
    <h4><a href='/news-releases/news-release-details/micron-first-release'>Micron First Release</a></h4>
    <div>Jul 16, 2026</div>
    <div>Source-provided first release summary.</div>
    <a href='/static-files/first.pdf'>PDF Version</a>
  </div>
  <div class='views-row'>
    <h4><a href='/news-releases/news-release-details/micron-second-release'>Micron Second Release</a></h4>
    <div>Jul 15, 2026</div>
    <div>Source-provided second release summary.</div>
    <a href='/static-files/second.pdf'>PDF Version</a>
  </div>
</body></html>
"""
NEWSROOM_URL = "https://www.micron.com/about/press/news"
NEWSROOM_HTML = b"""
<html><body>
  <h1>Newsroom</h1>
  <h2>Latest news</h2>
  <article>
    <h3>Micron Strengthens Automotive Ecosystem Supply Through Strategic Customer Agreements</h3>
    <time>July 16, 2026</time>
    <a href='https://investors.micron.com/news-releases/news-release-details/micron-strengthens-automotive-ecosystem-supply-through-strategic'>Read article</a>
  </article>
  <article>
    <h3>Micron Announces Participation in Investor Event</h3>
    <div>July 15, 2026</div>
    <a href='https://investors.micron.com/news-releases/news-release-details/micron-announces-participation-investor-event-4'>Read article</a>
  </article>
</body></html>
"""


class CompanySourceCompatTests(unittest.TestCase):
    def test_parses_historical_investor_release_index_entries(self) -> None:
        entries = parse_release_index(HISTORICAL_INDEX_HTML, index_url=HISTORICAL_INDEX_URL)
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0]["title"], "Micron First Release")
        self.assertEqual(entries[0]["published"], "Jul 16, 2026")
        self.assertEqual(entries[0]["summary"], "Source-provided first release summary.")
        self.assertEqual(
            entries[0]["link"],
            "https://investors.micron.com/news-releases/news-release-details/micron-first-release",
        )

    def test_parses_official_corporate_newsroom_cards(self) -> None:
        entries = parse_micron_newsroom_index(NEWSROOM_HTML, index_url=NEWSROOM_URL)
        self.assertEqual(len(entries), 2)
        self.assertEqual(
            entries[0]["title"],
            "Micron Strengthens Automotive Ecosystem Supply Through Strategic Customer Agreements",
        )
        self.assertEqual(entries[0]["published"], "July 16, 2026")
        self.assertEqual(
            entries[0]["link"],
            "https://investors.micron.com/news-releases/news-release-details/micron-strengthens-automotive-ecosystem-supply-through-strategic",
        )

    def test_collects_allowlisted_newsroom_index_without_article_fetches(self) -> None:
        requests: list[str] = []
        observed_limits: list[int | None] = []

        def fetcher(url: str, **kwargs: object) -> HttpResult:
            requests.append(url)
            observed_limits.append(kwargs.get("max_bytes") if isinstance(kwargs.get("max_bytes"), int) else None)
            return HttpResult(body=NEWSROOM_HTML, final_url=url, request_count=1, content_type="text/html")

        config = {
            "schema_version": "1.0.0",
            "sources": [
                {
                    "ticker": "MU",
                    "source_name": "Micron Newsroom",
                    "source_kind": "html_release_index",
                    "index_url": NEWSROOM_URL,
                    "allowed_hosts": ["micron.com"],
                }
            ],
        }
        records, metrics = collect_company_feeds_live(
            config,
            collected_at_utc="2026-07-18T00:00:00Z",
            user_agent="PPI Research contact@example.com",
            lookback_days=30,
            fetcher=fetcher,
        )
        self.assertEqual(requests, [NEWSROOM_URL])
        self.assertEqual(observed_limits, [HTML_RELEASE_INDEX_MAX_BYTES])
        self.assertEqual(len(records), 2)
        self.assertTrue(all(record["ticker"] == "MU" for record in records))
        self.assertTrue(all(record["source_name"] == "Micron Newsroom" for record in records))
        self.assertEqual(metrics["configured_source_count"], 1)
        self.assertEqual(metrics["html_index_pages_fetched"], 1)
        self.assertEqual(metrics["html_release_index_max_bytes"], HTML_RELEASE_INDEX_MAX_BYTES)
        self.assertEqual(metrics["failures"], [])
        self.assertFalse(metrics["article_pages_fetched"])

    def test_rejects_unsafe_html_index_host(self) -> None:
        config = {
            "schema_version": "1.0.0",
            "sources": [
                {
                    "ticker": "MU",
                    "source_name": "Micron Newsroom",
                    "source_kind": "html_release_index",
                    "index_url": "https://example.com/latest-news",
                    "allowed_hosts": ["micron.com"],
                }
            ],
        }
        with self.assertRaisesRegex(CollectorError, "index URL is not allowlisted"):
            collect_company_feeds_live(
                config,
                collected_at_utc="2026-07-18T00:00:00Z",
                user_agent="PPI Research contact@example.com",
                lookback_days=30,
            )


if __name__ == "__main__":
    unittest.main()
