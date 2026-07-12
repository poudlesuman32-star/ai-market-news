from __future__ import annotations

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

    def test_qualifying_candidate_is_bound_but_still_requires_manual_approval(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            news = self._write(root, "news.jsonl", [
                {"record_id": "sec-1", "provider": "sec_edgar"},
                {"record_id": "company-1", "provider": "official_company_source"},
            ])
            import hashlib
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
            })
            result = bind_public_input_contract(
                news_path=news,
                receipt_path=receipt,
                manifest_path=manifest,
                report_path=report,
                independent_path=independent,
            )
            self.assertEqual(result["contract_id"], CONTRACT_ID)
            self.assertEqual(result["contract_sha256"], CONTRACT_SHA256)
            self.assertEqual(result["status"], "candidate_ready_for_manual_authorization")
            self.assertEqual(result["blocked_external"], ["manual_approval_required"])
            self.assertFalse(result["publication_authorized"])
            self.assertFalse(result["official_r9_count_authorized"])

    def test_missing_sec_record_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            news = self._write(root, "news.jsonl", [{"record_id": "company-1", "provider": "official_company_source"}])
            import hashlib
            dataset_hash = hashlib.sha256(news.read_bytes()).hexdigest()
            receipt = self._write(root, "collection_receipt.json", {
                "candidate_only": True,
                "dataset_sha256": dataset_hash,
                "provider_counts": {"official_company_source": 1},
                "request_counts": {"sec": 3, "official_company_sources": 2},
                "provider_failures": [],
            })
            manifest = self._write(root, "news_manifest.preview.json", {"candidate_only": True, "file_sha256": dataset_hash})
            report = self._write(root, "run_report.json", {
                "candidate_only": True,
                "publication_enabled": False,
                "contents_write_permission_authorized": False,
                "external_writes_enabled": False,
                "published_to_repository": False,
                "provider_failures": [],
            })
            independent = self._write(root, "independent_validation.json", {
                "candidate_valid": False,
                "failures": ["accepted_sec_record_present"],
                "publication_authorized": False,
                "official_r9_count_authorized": False,
            })
            result = bind_public_input_contract(
                news_path=news,
                receipt_path=receipt,
                manifest_path=manifest,
                report_path=report,
                independent_path=independent,
            )
            self.assertEqual(result["status"], "validation_failed")
            self.assertIn("accepted_sec_record_present", result["failures"])
            self.assertIn("independent_validator_passed", result["failures"])


if __name__ == "__main__":
    unittest.main()
