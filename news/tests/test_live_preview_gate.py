from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from ai_market_news.enforce_live_preview_gate import GATE_VERSION, enforce_live_preview_gate


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def receipt(*, sec_records: int = 1, company_records: int = 1, sec_requests: int = 3, company_requests: int = 2) -> dict:
    provider_counts = {}
    if sec_records:
        provider_counts["sec_edgar"] = sec_records
    if company_records:
        provider_counts["official_company_source"] = company_records
    return {
        "collection_mode": "live_primary_sources",
        "request_counts": {
            "sec": sec_requests,
            "official_company_sources": company_requests,
            "polygon": 0,
            "finnhub": 0,
        },
        "provider_counts": provider_counts,
        "provider_failures": [],
    }


def report() -> dict:
    return {
        "workflow_event": "workflow_dispatch",
        "accepted_event_count": 2,
        "rejected_event_count": 0,
        "published_to_repository": False,
        "schedule_enabled": False,
        "this_run_qualifies": True,
    }


class LivePreviewGateTests(unittest.TestCase):
    def run_gate(self, receipt_value: dict, report_value: dict | None = None) -> dict:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            receipt_path = root / "collection_receipt.json"
            report_path = root / "run_report.json"
            write_json(receipt_path, receipt_value)
            write_json(report_path, report_value or report())
            result = enforce_live_preview_gate(receipt_path=receipt_path, report_path=report_path)
            self.assertEqual(result, json.loads(report_path.read_text(encoding="utf-8")))
            return result

    def test_mixed_sec_and_company_preview_qualifies(self) -> None:
        result = self.run_gate(receipt())
        self.assertTrue(result["this_run_qualifies"])
        self.assertEqual(result["live_primary_gate_version"], GATE_VERSION)
        self.assertEqual(result["qualification_exclusion_reasons"], [])
        self.assertTrue(all(result["live_primary_countability_checks"].values()))

    def test_requests_without_accepted_sec_records_do_not_qualify(self) -> None:
        result = self.run_gate(receipt(sec_records=0))
        self.assertFalse(result["this_run_qualifies"])
        self.assertIn("accepted_sec_record_present", result["qualification_exclusion_reasons"])

    def test_missing_official_company_request_does_not_qualify(self) -> None:
        result = self.run_gate(receipt(company_requests=0))
        self.assertFalse(result["this_run_qualifies"])
        self.assertIn("official_company_network_requests_recorded", result["qualification_exclusion_reasons"])

    def test_provider_failure_does_not_qualify(self) -> None:
        value = receipt()
        value["provider_failures"] = ["sec_edgar:AAPL:collection_failed"]
        result = self.run_gate(value)
        self.assertFalse(result["this_run_qualifies"])
        self.assertIn("provider_failures_empty", result["qualification_exclusion_reasons"])


if __name__ == "__main__":
    unittest.main()
