from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from ai_market_news.enforce_live_candidate_gate import GATE_VERSION, enforce_live_candidate_gate


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def receipt(*, sec_records: int = 1, company_records: int = 1) -> dict:
    provider_counts = {}
    if sec_records:
        provider_counts["sec_edgar"] = sec_records
    if company_records:
        provider_counts["official_company_source"] = company_records
    return {
        "collection_mode": "live_primary_sources",
        "candidate_only": True,
        "request_counts": {
            "sec": 3,
            "official_company_sources": 2,
            "polygon": 0,
            "finnhub": 0,
        },
        "provider_counts": provider_counts,
        "provider_failures": [],
    }


def report(*, workflow_event: str = "schedule") -> dict:
    return {
        "workflow_event": workflow_event,
        "schedule_enabled": workflow_event == "schedule",
        "candidate_only": True,
        "accepted_event_count": 2,
        "rejected_event_count": 0,
        "provider_failures": [],
        "publication_enabled": False,
        "published_to_repository": False,
        "contents_write_permission_authorized": False,
        "external_writes_enabled": False,
        "secrets_required": False,
    }


class LiveCandidateGateTests(unittest.TestCase):
    def run_gate(self, receipt_value: dict, report_value: dict) -> dict:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            receipt_path = root / "collection_receipt.json"
            report_path = root / "run_report.json"
            write_json(receipt_path, receipt_value)
            write_json(report_path, report_value)
            result = enforce_live_candidate_gate(receipt_path=receipt_path, report_path=report_path)
            self.assertEqual(result, json.loads(report_path.read_text(encoding="utf-8")))
            return result

    def test_scheduled_mixed_provider_candidate_qualifies(self) -> None:
        result = self.run_gate(receipt(), report())
        self.assertTrue(result["this_run_qualifies"])
        self.assertEqual(result["live_primary_gate_version"], GATE_VERSION)
        self.assertFalse(result["publication_authorized"])
        self.assertFalse(result["official_r9_count_authorized"])

    def test_manual_candidate_also_qualifies(self) -> None:
        result = self.run_gate(receipt(), report(workflow_event="workflow_dispatch"))
        self.assertTrue(result["this_run_qualifies"])

    def test_missing_sec_record_fails_closed(self) -> None:
        result = self.run_gate(receipt(sec_records=0), report())
        self.assertFalse(result["this_run_qualifies"])
        self.assertIn("accepted_sec_record_present", result["qualification_exclusion_reasons"])

    def test_write_permission_fails_closed(self) -> None:
        value = report()
        value["contents_write_permission_authorized"] = True
        result = self.run_gate(receipt(), value)
        self.assertFalse(result["this_run_qualifies"])
        self.assertIn("contents_write_disabled", result["qualification_exclusion_reasons"])

    def test_schedule_flag_mismatch_fails_closed(self) -> None:
        value = report()
        value["schedule_enabled"] = False
        result = self.run_gate(receipt(), value)
        self.assertFalse(result["this_run_qualifies"])
        self.assertIn("schedule_flag_matches_trigger", result["qualification_exclusion_reasons"])


if __name__ == "__main__":
    unittest.main()
