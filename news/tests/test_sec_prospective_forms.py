from __future__ import annotations

import unittest

from ai_market_news.collector_common import CollectorError
from ai_market_news.sec_adapter_compat import collect_sec_live, prospective_form_activations


class SecProspectiveFormTests(unittest.TestCase):
    def test_pre_activation_records_are_filtered_and_post_activation_records_are_retained(self) -> None:
        config = {
            "schema_version": "1.0.0",
            "forms": ["4"],
            "prospective_forms": [
                {"form": "144", "activated_at_utc": "2026-07-20T13:40:00Z"},
            ],
            "companies": [
                {"ticker": "AAPL", "cik": "0000320193", "company_name": "Apple Inc."},
            ],
        }
        payload = {
            "filings": {
                "recent": {
                    "accessionNumber": [
                        "0000320193-26-000201",
                        "0000320193-26-000202",
                        "0000320193-26-000203",
                    ],
                    "form": ["144", "144", "4"],
                    "acceptanceDateTime": [
                        "2026-07-20T13:39:59Z",
                        "2026-07-20T13:40:01Z",
                        "2026-07-20T13:00:00Z",
                    ],
                    "filingDate": ["2026-07-20", "2026-07-20", "2026-07-20"],
                    "reportDate": ["2026-07-20", "2026-07-20", "2026-07-20"],
                    "primaryDocument": ["pre.xml", "post.xml", "ownership.xml"],
                    "primaryDocDescription": ["Pre-activation notice", "Post-activation notice", "Ownership report"],
                    "items": ["", "", ""],
                }
            }
        }

        def fetcher(_url: str, **_kwargs: object):
            return payload, 1

        def forbidden_document_fetcher(_url: str, **_kwargs: object):
            self.fail("Forms 4 and 144 must remain metadata-only")

        records, metrics = collect_sec_live(
            config,
            collected_at_utc="2026-07-20T14:00:00Z",
            user_agent="PPI Test contact@example.com",
            lookback_days=30,
            fetcher=fetcher,
            document_fetcher=forbidden_document_fetcher,
        )

        self.assertEqual(
            [(record["filing_type"], record["provider_article_id"]) for record in records],
            [
                ("4", "0000320193-26-000203"),
                ("144", "0000320193-26-000202"),
            ],
        )
        self.assertEqual(metrics["record_count"], 2)
        self.assertEqual(metrics["prospective_record_count"], 1)
        self.assertEqual(metrics["prospective_pre_activation_filtered_count"], 1)
        self.assertEqual(
            metrics["prospective_form_activation_utc"],
            {"144": "2026-07-20T13:40:00Z"},
        )

    def test_rolling_and_prospective_forms_cannot_overlap(self) -> None:
        with self.assertRaisesRegex(CollectorError, "overlaps rolling form"):
            prospective_form_activations(
                {
                    "forms": ["4"],
                    "prospective_forms": [
                        {"form": "4", "activated_at_utc": "2026-07-20T13:40:00Z"},
                    ],
                }
            )

    def test_activation_timestamp_must_be_canonical_utc(self) -> None:
        for value in ("2026-07-20T13:40:00+00:00", "2026-07-20T13:40:00.000Z"):
            with self.subTest(value=value), self.assertRaises(CollectorError):
                prospective_form_activations(
                    {
                        "forms": ["4"],
                        "prospective_forms": [
                            {"form": "144", "activated_at_utc": value},
                        ],
                    }
                )

    def test_duplicate_prospective_forms_are_rejected(self) -> None:
        with self.assertRaisesRegex(CollectorError, "duplicate prospective SEC form"):
            prospective_form_activations(
                {
                    "forms": ["4"],
                    "prospective_forms": [
                        {"form": "144", "activated_at_utc": "2026-07-20T13:40:00Z"},
                        {"form": "144", "activated_at_utc": "2026-07-20T13:40:00Z"},
                    ],
                }
            )


if __name__ == "__main__":
    unittest.main()
