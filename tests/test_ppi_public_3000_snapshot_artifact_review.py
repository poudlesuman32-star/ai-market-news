from __future__ import annotations

import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REVIEWER_PATH = ROOT / "scripts" / "review_ppi_public_3000_snapshot_artifact.py"
SPEC = importlib.util.spec_from_file_location("step9_reviewer", REVIEWER_PATH)
reviewer = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(reviewer)
validator = reviewer.validator


class Step9ArtifactReviewTests(unittest.TestCase):
    def record(self, index: int) -> dict:
        figi = f"BBG{index:09d}"
        return {
            "candidate_id": f"candidate-{index:04d}",
            "cik": f"{index + 1:010d}",
            "ticker": f"T{index:04d}",
            "exchange": "NASDAQ",
            "disposition": "allocated",
            "instrument_id": validator.stable_instrument_id(figi),
            "figi": figi,
            "identity_status": "verified_exact_figi",
            "classification_status": "unresolved_asset_subtype",
            "source_row_sha256": f"{index:064x}",
        }

    def fixture(self, root: Path) -> None:
        instruments = b"".join(validator.canon(self.record(i)) for i in range(3000))
        deferred = b""
        (root / "universe-instruments-3000.jsonl").write_bytes(instruments)
        (root / "universe-deferred-3000.jsonl").write_bytes(deferred)
        hashes = {
            "universe-instruments-3000.jsonl": hashlib.sha256(instruments).hexdigest(),
            "universe-deferred-3000.jsonl": hashlib.sha256(deferred).hexdigest(),
        }
        combined = reviewer.canonical_json_sha256({name: hashes[name] for name in sorted(hashes)})
        manifest = {
            "contract_id": validator.CONTRACT_ID,
            "artifact_mode": "success",
            "data_file_sha256": hashes,
            "combined_snapshot_sha256": combined,
            "step8_source": {
                "review_run_id": 123,
                "review_run_attempt": 1,
                "review_artifact_id": 456,
                "review_receipt_sha256": "a" * 64,
            },
        }
        receipt = {
            "contract_id": validator.CONTRACT_ID,
            "artifact_mode": "success",
            "gate_passed": True,
            "total_candidate_dispositions": 3000,
            "combined_snapshot_sha256": combined,
        }
        (root / "manifest.json").write_bytes(validator.canon(manifest))
        (root / "receipt.json").write_bytes(validator.canon(receipt))
        (root / "report.md").write_text("# fixture\n", encoding="utf-8")

    def test_reviewer_recomputes_hashes_offline(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fixture(root)
            result = reviewer.review(root)
        self.assertTrue(result["gate_passed"])
        self.assertEqual(result["total_candidate_dispositions"], 3000)
        self.assertEqual(result["review_network_requests"], 0)

    def test_tampered_data_fails_hash_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fixture(root)
            path = root / "universe-instruments-3000.jsonl"
            path.write_bytes(path.read_bytes() + b"\n")
            with self.assertRaises(reviewer.ReviewError):
                reviewer.review(root)

    def test_wrong_combined_hash_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fixture(root)
            manifest = json.loads((root / "manifest.json").read_text())
            manifest["combined_snapshot_sha256"] = "0" * 64
            (root / "manifest.json").write_bytes(validator.canon(manifest))
            with self.assertRaises(reviewer.ReviewError):
                reviewer.review(root)

    def test_missing_step8_lineage_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fixture(root)
            manifest = json.loads((root / "manifest.json").read_text())
            del manifest["step8_source"]["review_artifact_id"]
            (root / "manifest.json").write_bytes(validator.canon(manifest))
            with self.assertRaises(reviewer.ReviewError):
                reviewer.review(root)

    def test_blocked_artifact_never_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "blocked.json").write_text('{"artifact_mode":"blocked"}\n', encoding="utf-8")
            (root / "report.md").write_text("# blocked\n", encoding="utf-8")
            result = reviewer.review(root)
        self.assertFalse(result["gate_passed"])
        self.assertEqual(result["artifact_mode"], "blocked")


if __name__ == "__main__":
    unittest.main()
