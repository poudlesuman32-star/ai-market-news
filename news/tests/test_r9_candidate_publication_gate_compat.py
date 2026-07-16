from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from ai_market_news.collector_common import CollectorError
from ai_market_news.enforce_live_preview_gate import enforce_live_preview_gate


class CandidatePublicationGateCompatibilityTests(unittest.TestCase):
    def write_json(self, root: Path, name: str, value: dict) -> Path:
        path = root / name
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    def candidate_receipt(self) -> dict:
        return {
            "collection_mode": "live_primary_sources",
            "candidate_only": True,
            "request_counts": {"sec": 1, "official_company_sources": 1},
            "provider_counts": {"sec_edgar": 1, "official_company_source": 1},
            "provider_failures": [],
        }

    def candidate_report(self) -> dict:
        return {
            "workflow_event": "workflow_dispatch",
            "schedule_enabled": False,
            "candidate_only": True,
            "provider_failures": [],
            "accepted_event_count": 2,
            "rejected_event_count": 0,
            "publication_enabled": False,
            "published_to_repository": False,
            "contents_write_permission_authorized": False,
            "external_writes_enabled": False,
            "secrets_required": False,
        }

    def test_candidate_artifact_is_delegated_to_candidate_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            receipt = self.write_json(root, "receipt.json", self.candidate_receipt())
            report = self.write_json(root, "report.json", self.candidate_report())
            result = enforce_live_preview_gate(receipt_path=receipt, report_path=report)
            self.assertTrue(result["this_run_qualifies"])
            self.assertEqual(result["live_primary_gate_version"], "live-primary-candidate-v1")
            self.assertFalse(result["publication_authorized"])
            self.assertFalse(result["official_r9_count_authorized"])

    def test_candidate_marker_disagreement_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            receipt_value = self.candidate_receipt()
            receipt_value["candidate_only"] = False
            receipt = self.write_json(root, "receipt.json", receipt_value)
            report = self.write_json(root, "report.json", self.candidate_report())
            with self.assertRaises(CollectorError):
                enforce_live_preview_gate(receipt_path=receipt, report_path=report)


if __name__ == "__main__":
    unittest.main()
