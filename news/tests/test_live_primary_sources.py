from __future__ import annotations

import hashlib
import unittest

from ai_market_news.collector_common import CollectorError
from ai_market_news.company_feed_adapter import collect_company_feeds_live
from ai_market_news.live_http import HttpResult, host_is_allowed
from ai_market_news.sec_adapter import collect_sec_live

COLLECTED_AT = "2026-07-10T18:00:00Z"


class LivePrimarySourceTests(unittest.TestCase):
    def test_sec_live_fetches_bounded_primary_and_exhibit_evidence(self) -> None:
        config = {
            "schema_version": "1.0.0",
            "forms": ["8-K", "10-Q"],
            "companies": [
                {"ticker": "NVDA", "cik": "0001045810", "company_name": "NVIDIA Corporation"}
            ],
        }
        payload = {
            "filings": {
                "recent": {
                    "accessionNumber": ["0001045810-26-000123", "0001045810-26-000122"],
                    "form": ["8-K", "4"],
                    "acceptanceDateTime": ["2026-07-10T12:34:56.000Z", "2026-07-10T10:00:00.000Z"],
                    "filingDate": ["2026-07-10", "2026-07-10"],
                    "reportDate": ["2026-07-09", "2026-07-09"],
                    "primaryDocument": ["nvda-20260709.htm", "ownership.xml"],
                    "primaryDocDescription": ["Current report", "Ownership report"],
                    "items": ["2.02,9.01", ""],
                }
            }
        }
        primary_body = b"<html><body>Current report furnishing the attached earnings release.</body></html>"
        index_body = b"""<html><body><table>
        <tr><th>Seq</th><th>Description</th><th>Document</th><th>Type</th></tr>
        <tr><td>1</td><td>Current report</td><td><a href='nvda-20260709.htm'>nvda-20260709.htm</a></td><td>8-K</td></tr>
        <tr><td>2</td><td>Earnings release</td><td><a href='ex991-earnings.htm'>ex991-earnings.htm</a></td><td>EX-99.1</td></tr>
        </table></body></html>"""
        exhibit_body = b"""<html><head><style>hidden</style></head><body>
        <h1>Quarterly earnings</h1><p>Revenue increased and management raised guidance.</p>
        <script>ignored()</script></body></html>"""

        def fetcher(url, **kwargs):
            self.assertEqual(url, "https://data.sec.gov/submissions/CIK0001045810.json")
            self.assertEqual(kwargs["allowed_hosts"], {"sec.gov"})
            self.assertIn("contact@example.com", kwargs["user_agent"])
            return payload, 1

        def document_fetcher(url, **kwargs):
            self.assertEqual(kwargs["allowed_hosts"], {"sec.gov"})
            self.assertEqual(kwargs["max_bytes"], 1_500_000)
            if url.endswith("nvda-20260709.htm"):
                body = primary_body
            elif url.endswith("0001045810-26-000123-index.html"):
                body = index_body
            elif url.endswith("ex991-earnings.htm"):
                body = exhibit_body
            else:
                self.fail(f"unexpected SEC document URL: {url}")
            return HttpResult(body=body, final_url=url, request_count=1, content_type="text/html; charset=utf-8")

        records, metrics = collect_sec_live(
            config,
            collected_at_utc=COLLECTED_AT,
            user_agent="PPI Test contact@example.com",
            lookback_days=7,
            fetcher=fetcher,
            document_fetcher=document_fetcher,
        )
        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertEqual(record["ticker"], "NVDA")
        self.assertEqual(record["filing_type"], "8-K")
        self.assertEqual(record["provider_article_id"], "0001045810-26-000123")
        self.assertIn("/Archives/edgar/data/1045810/000104581026000123/", record["source_url"])
        self.assertIn("attached earnings release", record["summary"])
        self.assertIn("Quarterly earnings", record["summary"])
        self.assertIn("raised guidance", record["summary"])
        self.assertNotIn("ignored()", record["summary"])
        self.assertFalse(record["synthetic_content_used"])
        self.assertFalse(record["source_content_modified"])
        self.assertEqual(metrics["request_count"], 4)
        self.assertEqual(metrics["failures"], [])
        self.assertTrue(metrics["full_document_content_fetched"])
        self.assertEqual(metrics["primary_document_fetch_count"], 1)
        self.assertEqual(metrics["exhibit_document_fetch_count"], 1)
        self.assertEqual(
            metrics["primary_document_sha256"]["0001045810-26-000123"],
            hashlib.sha256(primary_body).hexdigest(),
        )
        self.assertEqual(
            metrics["exhibit_document_sha256"]["0001045810-26-000123"]["ex991-earnings.htm"],
            hashlib.sha256(exhibit_body).hexdigest(),
        )

    def test_sec_form4_is_not_document_fetched(self) -> None:
        config = {
            "schema_version": "1.0.0",
            "forms": ["4"],
            "companies": [{"ticker": "AAPL", "cik": "0000320193", "company_name": "Apple Inc."}],
        }
        payload = {
            "filings": {
                "recent": {
                    "accessionNumber": ["0000320193-26-000111"],
                    "form": ["4"],
                    "acceptanceDateTime": ["2026-07-10T12:00:00Z"],
                    "filingDate": ["2026-07-10"],
                    "reportDate": ["2026-07-10"],
                    "primaryDocument": ["ownership.xml"],
                    "primaryDocDescription": ["Ownership report"],
                    "items": [""],
                }
            }
        }

        def fetcher(url, **kwargs):
            return payload, 1

        def forbidden_document_fetcher(url, **kwargs):
            self.fail("Form 4 must not fetch a primary document, filing index, or exhibit")

        records, metrics = collect_sec_live(
            config,
            collected_at_utc=COLLECTED_AT,
            user_agent="PPI Test contact@example.com",
            lookback_days=7,
            fetcher=fetcher,
            document_fetcher=forbidden_document_fetcher,
        )
        self.assertEqual(len(records), 1)
        self.assertFalse(metrics["full_document_content_fetched"])
        self.assertEqual(metrics["primary_document_fetch_count"], 0)
        self.assertEqual(metrics["primary_document_sha256"], {})
        self.assertEqual(metrics["exhibit_document_fetch_count"], 0)
        self.assertEqual(metrics["exhibit_document_sha256"], {})

    def test_sec_rejects_unsafe_exhibit_path(self) -> None:
        config = {
            "schema_version": "1.0.0",
            "forms": ["8-K"],
            "companies": [{"ticker": "AAPL", "cik": "0000320193", "company_name": "Apple Inc."}],
        }
        payload = {
            "filings": {
                "recent": {
                    "accessionNumber": ["0000320193-26-000111"],
                    "form": ["8-K"],
                    "acceptanceDateTime": ["2026-07-10T12:00:00Z"],
                    "filingDate": ["2026-07-10"],
                    "reportDate": ["2026-07-10"],
                    "primaryDocument": ["aapl-8k.htm"],
                    "primaryDocDescription": ["Current report"],
                    "items": ["8.01"],
                }
            }
        }
        unsafe_index = b"<table><tr><td><a href='../outside.htm'>outside</a></td><td>EX-99.1</td></tr></table>"

        def fetcher(url, **kwargs):
            return payload, 1

        def document_fetcher(url, **kwargs):
            body = unsafe_index if url.endswith("-index.html") else b"<html><body>Current report.</body></html>"
            return HttpResult(body=body, final_url=url, request_count=1, content_type="text/html")

        records, metrics = collect_sec_live(
            config,
            collected_at_utc=COLLECTED_AT,
            user_agent="PPI Test contact@example.com",
            lookback_days=7,
            fetcher=fetcher,
            document_fetcher=document_fetcher,
        )
        self.assertEqual(records, [])
        self.assertEqual(metrics["failures"], ["sec_edgar:AAPL:collection_failed"])

    def test_sec_failure_is_isolated(self) -> None:
        config = {
            "schema_version": "1.0.0",
            "forms": ["8-K"],
            "companies": [
                {"ticker": "AAPL", "cik": "0000320193", "company_name": "Apple Inc."},
                {"ticker": "MU", "cik": "0000723125", "company_name": "Micron Technology, Inc."},
            ],
        }
        valid = {
            "filings": {
                "recent": {
                    "accessionNumber": ["0000320193-26-000111"],
                    "form": ["8-K"],
                    "acceptanceDateTime": ["2026-07-10T12:00:00Z"],
                    "filingDate": ["2026-07-10"],
                    "reportDate": ["2026-07-10"],
                    "primaryDocument": ["aapl-8k.htm"],
                    "primaryDocDescription": ["Current report"],
                    "items": ["8.01"],
                }
            }
        }

        def fetcher(url, **kwargs):
            if "0000723125" in url:
                raise CollectorError("simulated provider failure")
            return valid, 1

        def document_fetcher(url, **kwargs):
            body = b"<html><body><table></table></body></html>" if url.endswith("-index.html") else b"<html><body>Apple announced a financing agreement.</body></html>"
            return HttpResult(body=body, final_url=url, request_count=1, content_type="text/html")

        records, metrics = collect_sec_live(
            config,
            collected_at_utc=COLLECTED_AT,
            user_agent="PPI Test contact@example.com",
            lookback_days=7,
            fetcher=fetcher,
            document_fetcher=document_fetcher,
        )
        self.assertEqual([record["ticker"] for record in records], ["AAPL"])
        self.assertEqual(metrics["failures"], ["sec_edgar:MU:collection_failed"])

    def test_official_rss_and_atom_are_metadata_only(self) -> None:
        config = {
            "schema_version": "1.0.0",
            "sources": [
                {
                    "ticker": "AAPL",
                    "source_name": "Apple Newsroom",
                    "feed_url": "https://www.apple.com/newsroom/rss-feed.rss",
                    "allowed_hosts": ["apple.com"],
                },
                {
                    "ticker": "NVDA",
                    "source_name": "NVIDIA Newsroom",
                    "feed_url": "https://nvidianews.nvidia.com/rss.xml",
                    "allowed_hosts": ["nvidia.com"],
                },
            ],
        }
        rss = b"""<?xml version='1.0'?>
        <rss><channel><item>
          <title>Apple announces a new infrastructure program</title>
          <link>https://www.apple.com/newsroom/2026/07/example/</link>
          <guid>aapl-release-1</guid>
          <pubDate>Fri, 10 Jul 2026 12:00:00 GMT</pubDate>
          <description><![CDATA[<p>Apple provided an official source summary.</p>]]></description>
        </item></channel></rss>"""
        atom = b"""<?xml version='1.0'?>
        <feed xmlns='http://www.w3.org/2005/Atom'><entry>
          <title>NVIDIA announces expanded AI capacity</title>
          <link rel='alternate' href='https://nvidianews.nvidia.com/news/example'/>
          <id>nvda-release-1</id>
          <updated>2026-07-10T13:00:00Z</updated>
          <summary>Official NVIDIA feed summary.</summary>
        </entry></feed>"""

        def fetcher(url, **kwargs):
            body = rss if "apple.com" in url else atom
            return HttpResult(body=body, final_url=url, request_count=1, content_type="application/xml")

        records, metrics = collect_company_feeds_live(
            config,
            collected_at_utc=COLLECTED_AT,
            user_agent="PPI ai-market-news",
            lookback_days=7,
            fetcher=fetcher,
        )
        self.assertEqual([record["ticker"] for record in records], ["AAPL", "NVDA"])
        self.assertEqual(records[0]["summary"], "Apple provided an official source summary.")
        self.assertEqual(records[1]["summary"], "Official NVIDIA feed summary.")
        self.assertEqual(metrics["request_count"], 2)
        self.assertEqual(metrics["failures"], [])
        self.assertFalse(metrics["article_pages_fetched"])

    def test_off_host_release_link_fails_that_source(self) -> None:
        config = {
            "schema_version": "1.0.0",
            "sources": [
                {
                    "ticker": "AAPL",
                    "source_name": "Apple Newsroom",
                    "feed_url": "https://www.apple.com/newsroom/rss-feed.rss",
                    "allowed_hosts": ["apple.com"],
                }
            ],
        }
        body = b"""<rss><channel><item>
          <title>Unexpected link</title>
          <link>https://example.com/not-official</link>
          <guid>bad-link</guid>
          <pubDate>Fri, 10 Jul 2026 12:00:00 GMT</pubDate>
          <description>Source summary.</description>
        </item></channel></rss>"""

        def fetcher(url, **kwargs):
            return HttpResult(body=body, final_url=url, request_count=1, content_type="application/xml")

        records, metrics = collect_company_feeds_live(
            config,
            collected_at_utc=COLLECTED_AT,
            user_agent="PPI ai-market-news",
            lookback_days=7,
            fetcher=fetcher,
        )
        self.assertEqual(records, [])
        self.assertEqual(metrics["failures"], ["official_company_source:AAPL:collection_failed"])

    def test_host_allowlist_accepts_subdomains_only(self) -> None:
        self.assertTrue(host_is_allowed("https://nvidianews.nvidia.com/rss.xml", {"nvidia.com"}))
        self.assertFalse(host_is_allowed("https://nvidia.com.example.org/rss.xml", {"nvidia.com"}))
        self.assertFalse(host_is_allowed("http://nvidia.com/rss.xml", {"nvidia.com"}))


if __name__ == "__main__":
    unittest.main()
