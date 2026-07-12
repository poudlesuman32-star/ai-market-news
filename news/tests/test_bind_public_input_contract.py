from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from ai_market_news.bind_public_input_contract import CONTRACT_ID, CONTRACT_SHA256, bind_public_input_contract


class PublicInputContractBindingTests(unittest.TestCase):
    def _write(self, root: Path, name: str, value: object) -> Path:
        path = root / name
        if name.endswith(".jsonl"):
            path.write_text("\n".join(json.dumps(item, sort_keys=True) for item in value) + "\n", encoding="utf-8")
        else:
            path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return path

    def _inputs(self, root: Path) -> tuple[Path, Path, Path, Path, Path]:
        news = self._write(root, "news.jsonl", [
            {"record_id": "sec-1", "provider": "sec_edgar"},
            {"record_id": "company-1", "provider": "official_company_source"},
        ])
        dataset_hash = hashlib.sha256(news.read_bytes()).hexdigest()
        receipt = self._write(root, "collection_receipt.json", {
            "candidate_only": True,
            "dataset_sha256": dataset_hash,
            "provider_counts": {"sec_edgar": 1, "official_company_source": 1},
            "request_counts": {"sec": 3, "official_company_sources": 2},
            "provider_failures": [],
        })
        manifest = self._write(root, "news_manifest.preview.json", {
            "candidate_only": True,
            "file_sha256": dataset_hash,
        })
        report = self._write(root, "run_report.json", {
            "candidate_only": True,
            "publication_enabled": False,
            "contents_write_permission_authorized": False,
            "external_writes_enabled": False,
            "published_to_repository": False,
            "provider_failures": [],
        })
        independent = self._write(root, "independent_validation.json", {
            "candidate_valid": True,
            "failures": [],
            "publication_authorized": False,
            "official_r9_count_authorized": False,
            "input_sha256": {
                "news.jsonl": hashlib.sha256(news.read_bytes()).hexdigest(),
                "collection_receipt.json": hashlib.sha256(receipt.read_bytes()).hexdigest(),
                "news_manifest.preview.json": hashlib.sha256(manifest.read_bytes()).hexdigest(),
                "run_report.json": hashlib.sha256(report.read_bytes()).hexdigest(),
            },
        })
        return news, receipt, manifest, report, independent

    def test_qualifying_candidate_is_bound_but_still_requires_manual_approval(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            inputs = self._inputs(Path(directory))
            result = bind_public_input_contract(
                news_path=inputs[0], receipt_path=inputs[1], manifest_path=inputs[2], report_path=inputs[3], independent_path=inputs[4]
            )
            self.assertEqual(result["contract_id"], CONTRACT_ID)
            self.assertEqual(result["contract_sha256"], CONTRACT_SHA256)
            self.assertEqual(result["status"], "candidate_ready_for_manual_authorization")
            self.assertEqual(result["blocked_external"], ["manual_approval_required"])
            self.assertTrue(result["checks"]["independent_input_hashes_match"])
            self.assertFalse(result["publication_authorized"])
            self.assertFalse(result["official_r9_count_authorized"])

    def test_stale_independent_validation_artifact_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            news, receipt, manifest, report, independent = self._inputs(root)
            stale = json.loads(independent.read_text(encoding="utf-8"))
            stale["input_sha256"]["news.jsonl"] = "0" * 64
            independent.write_text(json.dumps(stale, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            result = bind_public_input_contract(
                news_path=news, receipt_path=receipt, manifest_path=manifest, report_path=report, independent_path=independent
            )
            self.assertEqual(result["status"], "validation_failed")
            self.assertIn("independent_input_hashes_match", result["failures"])

    def test_missing_sec_record_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            news, receipt, manifest, report, independent = self._inputs(root)
            receipt_value = json.loads(receipt.read_text(encoding="utf-8"))
            receipt_value["provider_counts"].pop("sec_edgar")
            receipt.write_text(json.dumps(receipt_value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            independent_value = json.loads(independent.read_text(encoding="utf-8"))
            independent_value["candidate_valid"] = False
            independent_value["failures"] = ["accepted_sec_record_present"]
            independent_value["input_sha256"]["collection_receipt.json"] = hashlib.sha256(receipt.read_bytes()).hexdigest()
            independent.write_text(json.dumps(independent_value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            result = bind_public_input_contract(
                news_path=news, receipt_path=receipt, manifest_path=manifest, report_path=report, independent_path=independent
            )
            self.assertEqual(result["status"], "validation_failed")
            self.assertIn("accepted_sec_record_present", result["failures"])
            self.assertIn("independent_validator_passed", result["failures"])


if __name__ == "__main__":
    unittest.main()
