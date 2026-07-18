from __future__ import annotations

import copy
import unittest

from ai_market_news.verify_live_source_coverage import EXPECTED_DOCUMENT_LIMITS, assess_live_source_coverage


COMPANY_CONFIG = {
    "schema_version": "1.0.0",
    "sources": [
        {"ticker": "AAPL", "source_kind": "feed"},
        {"ticker": "MU", "source_kind": "html_release_index"},
        {"ticker": "NVDA", "source_kind": "feed"},
    ],
}
SEC_CONFIG = {
    "schema_version": "1.0.0",
    "companies": [{"ticker": "AAPL"}, {"ticker": "MU"}, {"ticker": "NVDA"}],
}
COMPANY_METRICS = {
    "provider": "official_company_source",
    "configured_source_count": 3,
    "source_kind_counts": {"feed": 2, "html_release_index": 1},
    "request_count": 3,
    "failures": [],
}
SEC_METRICS = {
    "provider": "sec_edgar",
    "request_count": 12,
    "failures": [],
    "enrichment_failures": [],
    "enrichment_skips": ["sec_edgar:NVDA:accession:filing_index:no_substantive_exhibit_present"],
    "document_byte_limits": EXPECTED_DOCUMENT_LIMITS,
}
COMPANY_RECORDS = [{"ticker": "AAPL"}, {"ticker": "MU"}, {"ticker": "NVDA"}]
SEC_RECORDS = [{"ticker": "AAPL"}, {"ticker": "MU"}, {"ticker": "NVDA"}]


class LiveSourceCoverageVerificationTests(unittest.TestCase):
    def assess(
        self,
        *,
        company_metrics: dict[str, object] | None = None,
        sec_metrics: dict[str, object] | None = None,
        company_records: list[dict[str, object]] | None = None,
        sec_records: list[dict[str, object]] | None = None,
    ) -> dict[str, object]:
        return assess_live_source_coverage(
            company_config=copy.deepcopy(COMPANY_CONFIG),
            sec_config=copy.deepcopy(SEC_CONFIG),
            company_metrics=copy.deepcopy(company_metrics or COMPANY_METRICS),
            sec_metrics=copy.deepcopy(sec_metrics or SEC_METRICS),
            company_records=copy.deepcopy(company_records or COMPANY_RECORDS),
            sec_records=copy.deepcopy(sec_records or SEC_RECORDS),
        )

    def test_complete_live_coverage_validates_without_enabling_mutation(self) -> None:
        report = self.assess()
        self.assertEqual(report["status"], "validated")
        self.assertTrue(report["coverage_valid"])
        self.assertEqual(report["failed_checks"], [])
        self.assertEqual(report["company_record_counts"]["MU"], 1)
        self.assertEqual(report["sec_enrichment_skip_count"], 1)
        self.assertFalse(report["publication_enabled"])
        self.assertFalse(report["repository_mutation_enabled"])

    def test_missing_html_index_record_fails_closed(self) -> None:
        report = self.assess(company_records=[{"ticker": "AAPL"}, {"ticker": "NVDA"}])
        self.assertFalse(report["coverage_valid"])
        self.assertIn("html_release_index_returned_records", report["failed_checks"])

    def test_response_too_large_enrichment_failure_fails_closed(self) -> None:
        metrics = copy.deepcopy(SEC_METRICS)
        metrics["enrichment_failures"] = ["sec_edgar:MU:accession:primary_document:response_too_large"]
        report = self.assess(sec_metrics=metrics)
        self.assertIn("sec_enrichment_failures_empty", report["failed_checks"])
        self.assertIn("no_response_too_large_failure", report["failed_checks"])

    def test_missing_configured_sec_entity_fails_closed(self) -> None:
        report = self.assess(sec_records=[{"ticker": "AAPL"}, {"ticker": "MU"}])
        self.assertIn("sec_all_configured_entities_returned_records", report["failed_checks"])

    def test_document_limit_drift_fails_closed(self) -> None:
        metrics = copy.deepcopy(SEC_METRICS)
        metrics["document_byte_limits"] = {**EXPECTED_DOCUMENT_LIMITS, "primary_document": 10_000_000}
        report = self.assess(sec_metrics=metrics)
        self.assertIn("sec_document_limits_exact", report["failed_checks"])

    def test_provider_failure_fails_closed(self) -> None:
        metrics = copy.deepcopy(COMPANY_METRICS)
        metrics["failures"] = ["official_company_source:MU:collection_failed"]
        report = self.assess(company_metrics=metrics)
        self.assertIn("company_provider_failures_empty", report["failed_checks"])


if __name__ == "__main__":
    unittest.main()
