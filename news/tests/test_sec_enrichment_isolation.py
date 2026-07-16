from __future__ import annotations

import unittest

from ai_market_news.collector_common import CollectorError
from ai_market_news.live_http import HttpResult
from ai_market_news.sec_adapter import collect_sec_live


class SecEnrichmentIsolationTests(unittest.TestCase):
    def test_primary_document_failure_preserves_metadata_and_is_not_provider_failure(self) -> None:
        config = {
            "schema_version": "1.0.0",
            "forms": ["8-K"],
            "companies": [{"ticker": "MU", "cik": "0000723125", "company_name": "Micron Technology, Inc."}],
        }
        payload = {
            "filings": {"recent": {
                "accessionNumber": ["0000723125-26-000013"],
                "form": ["8-K"],
                "acceptanceDateTime": ["2026-06-24T16:01:00Z"],
                "filingDate": ["2026-06-24"],
                "reportDate": ["2026-05-28"],
                "primaryDocument": ["mu-20260624.htm"],
                "primaryDocDescription": ["Current report"],
                "items": ["2.02,9.01"],
            }}
        }

        def fetcher(url, **kwargs):
            return payload, 1

        def document_fetcher(url, **kwargs):
            raise CollectorError("response exceeds 1500000 bytes")

        records, metrics = collect_sec_live(
            config,
            collected_at_utc="2026-07-16T20:44:00Z",
            user_agent="PPI Test contact@example.com",
            lookback_days=30,
            fetcher=fetcher,
            document_fetcher=document_fetcher,
        )

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["provider_article_id"], "0000723125-26-000013")
        self.assertNotIn("Verified primary-document excerpt", records[0]["summary"])
        self.assertEqual(metrics["failures"], [])
        self.assertEqual(
            metrics["enrichment_failures"],
            ["sec_edgar:MU:0000723125-26-000013:primary_document:response_too_large"],
        )

    def test_index_failure_keeps_primary_evidence_and_classifies_stage(self) -> None:
        config = {
            "schema_version": "1.0.0",
            "forms": ["8-K"],
            "companies": [{"ticker": "MU", "cik": "0000723125", "company_name": "Micron Technology, Inc."}],
        }
        payload = {
            "filings": {"recent": {
                "accessionNumber": ["0000723125-26-000013"],
                "form": ["8-K"],
                "acceptanceDateTime": ["2026-06-24T16:01:00Z"],
                "filingDate": ["2026-06-24"],
                "reportDate": ["2026-05-28"],
                "primaryDocument": ["mu-20260624.htm"],
                "primaryDocDescription": ["Current report"],
                "items": ["2.02,9.01"],
            }}
        }

        def fetcher(url, **kwargs):
            return payload, 1

        def document_fetcher(url, **kwargs):
            if url.endswith("mu-20260624.htm"):
                return HttpResult(
                    body=b"<html><body>Micron announced financial results.</body></html>",
                    final_url=url,
                    request_count=1,
                    content_type="text/html",
                )
            raise CollectorError("HTTP 403 while fetching allowlisted primary source")

        records, metrics = collect_sec_live(
            config,
            collected_at_utc="2026-07-16T20:44:00Z",
            user_agent="PPI Test contact@example.com",
            lookback_days=30,
            fetcher=fetcher,
            document_fetcher=document_fetcher,
        )

        self.assertIn("financial results", records[0]["summary"])
        self.assertEqual(metrics["failures"], [])
        self.assertEqual(
            metrics["enrichment_failures"],
            ["sec_edgar:MU:0000723125-26-000013:filing_index:http_403"],
        )
        self.assertEqual(metrics["primary_document_fetch_count"], 1)
        self.assertEqual(metrics["exhibit_document_fetch_count"], 0)


if __name__ == "__main__":
    unittest.main()
