from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "reviewer", ROOT / "scripts" / "review_stable_instrument_id_allocation.py"
)
reviewer = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(reviewer)
allocator = reviewer.allocator


class StableIdAllocationArtifactReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.artifact = self.base / "artifact"
        self.output = self.base / "output"
        self.run_json = self.base / "run.json"
        self.source_contract = (
            ROOT
            / "contracts"
            / "PPI-STABLE-INSTRUMENT-ID-ALLOCATION-PILOT-001-R1.json"
        )
        self.review_contract = (
            ROOT
            / "contracts"
            / "PPI-STABLE-INSTRUMENT-ID-ALLOCATION-ARTIFACT-REVIEW-001-R1.json"
        )
        self.artifact.mkdir()
        self._build_success_artifact()
        self._write_json(
            self.run_json,
            {
                "id": 31,
                "run_attempt": 1,
                "name": reviewer.SOURCE_WORKFLOW_NAME,
                "repository": {"full_name": reviewer.EXPECTED_REPOSITORY},
                "head_branch": "main",
                "status": "completed",
                "conclusion": "success",
            },
        )

    def tearDown(self):
        self.temp.cleanup()

    @staticmethod
    def _write_json(path: Path, value: dict) -> None:
        path.write_text(
            json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

    @staticmethod
    def _candidate_id(index: int) -> str:
        return f"ppi-sec-seed-{index:024x}"

    @staticmethod
    def _figi(index: int) -> str:
        return f"BBG{index + 1:09d}"

    def _record(self, index: int) -> dict:
        common = {
            "candidate_id": self._candidate_id(index),
            "cik": f"{index + 1:010d}",
            "ticker": f"T{index:04d}",
            "exchange": ["NYSE", "NASDAQ", "NYSE_AMERICAN"][index % 3],
            "source_row_sha256": reviewer.digest(f"row-{index}".encode()),
            "mapping_record_sha256": reviewer.digest(f"mapping-{index}".encode()),
        }
        if index < 300:
            figi = self._figi(index)
            return {
                **common,
                "mapping_status": "exact",
                "allocation_status": "allocated",
                "instrument_id": allocator.stable_instrument_id(figi),
                "identity_key_type": "FIGI",
                "identity_key_value": figi,
                "figi": figi,
                "composite_figi": f"BBG{index + 1001:09d}",
                "share_class_figi": f"BBG{index + 2001:09d}",
                "identity_input_sha256": reviewer.digest(
                    allocator.identity_input(figi)
                ),
            }
        status = "ambiguous" if index < 400 else "unmatched"
        return {
            **common,
            "mapping_status": status,
            "allocation_status": f"deferred_{status}",
            "instrument_id": None,
            "identity_key_type": None,
            "identity_key_value": None,
            "figi": None,
            "composite_figi": None,
            "share_class_figi": None,
            "identity_input_sha256": None,
        }

    def _build_success_artifact(self) -> None:
        records = [self._record(index) for index in range(500)]
        snapshot = b"".join(reviewer.canon(record) for record in records)
        (self.artifact / "instrument-id-allocation-500.jsonl").write_bytes(
            snapshot
        )
        allocation_counts = {
            "allocated": 300,
            "deferred_ambiguous": 100,
            "deferred_unmatched": 100,
        }
        mapping_counts = {"exact": 300, "ambiguous": 100, "unmatched": 100}
        core = {
            "schema_version": "1.0.0",
            "contract_id": reviewer.SOURCE_CONTRACT_ID,
            "generated_at_utc": "2026-07-28T00:00:00Z",
            "algorithm": "sha256_figi_namespace_v1",
            "instrument_id_prefix": "ppi-us-equity-",
            "review_run_id": 22,
            "review_run_attempt": 1,
            "source_run_id": 21,
            "source_run_attempt": 1,
            "source_snapshot_sha256": reviewer.digest(b"sec"),
            "mapping_snapshot_sha256": reviewer.digest(b"mapping"),
            "candidate_count": 500,
            "mapping_counts": mapping_counts,
            "allocation_counts": allocation_counts,
            "allocation_snapshot_sha256": reviewer.digest(snapshot),
            "ambiguous_and_unmatched_preserved": True,
            "network_requests_performed": 0,
        }
        manifest = {
            **core,
            "manifest_core_sha256": reviewer.digest(reviewer.canon(core)),
        }
        self._write_json(self.artifact / "manifest.json", manifest)
        self._write_json(
            self.artifact / "receipt.json",
            {
                "schema_version": "1.0.0",
                "contract_id": reviewer.SOURCE_CONTRACT_ID,
                "contract_sha256": reviewer.digest(self.source_contract.read_bytes()),
                "repository": reviewer.EXPECTED_REPOSITORY,
                "run_id": "31",
                "run_attempt": "1",
                "event_name": "workflow_run",
                "head_sha": "a" * 40,
                "generated_at_utc": "2026-07-28T00:00:00Z",
                "allocation_snapshot_sha256": manifest[
                    "allocation_snapshot_sha256"
                ],
                "mapping_snapshot_sha256": manifest["mapping_snapshot_sha256"],
                "manifest_core_sha256": manifest["manifest_core_sha256"],
                "stable_instrument_ids_allocated": 300,
                "ambiguous_deferred": 100,
                "unmatched_deferred": 100,
                "network_requests_performed": 0,
                "private_access": False,
                "screening": False,
                "deep_evidence_collection": False,
                "private_dispatch": False,
                "billing_budget_mutation": False,
                "registry_mutation": False,
                "production": False,
                "publication": False,
                "trading": False,
                "authorized_actions": [
                    "stable_instrument_id_allocation_public_pilot"
                ],
            },
        )
        (self.artifact / "report.md").write_text(
            "# Allocation\n\n- Status: success\n- Candidates: 500\n"
            "- Allocated: 300\n- Deferred ambiguous: 100\n"
            "- Deferred unmatched: 100\n",
            encoding="utf-8",
        )

    def _rewrite_snapshot(self, records: list[dict]) -> None:
        snapshot = b"".join(reviewer.canon(record) for record in records)
        (self.artifact / "instrument-id-allocation-500.jsonl").write_bytes(
            snapshot
        )
        manifest = json.loads((self.artifact / "manifest.json").read_text())
        core = {
            key: value
            for key, value in manifest.items()
            if key != "manifest_core_sha256"
        }
        core["allocation_snapshot_sha256"] = reviewer.digest(snapshot)
        manifest = {
            **core,
            "manifest_core_sha256": reviewer.digest(reviewer.canon(core)),
        }
        self._write_json(self.artifact / "manifest.json", manifest)
        receipt = json.loads((self.artifact / "receipt.json").read_text())
        receipt["allocation_snapshot_sha256"] = manifest[
            "allocation_snapshot_sha256"
        ]
        receipt["manifest_core_sha256"] = manifest["manifest_core_sha256"]
        self._write_json(self.artifact / "receipt.json", receipt)

    def test_contract_is_review_only(self):
        contract = json.loads(self.review_contract.read_text())
        self.assertEqual(contract["authorized_actions"], [])
        self.assertFalse(contract["authority"]["universe_snapshot_assembly"])
        self.assertFalse(contract["authority"]["private_access"])
        self.assertFalse(contract["authority"]["registry_mutation"])

    def test_workflow_is_read_only_and_source_bound(self):
        text = (
            ROOT
            / ".github/workflows/ppi-stable-instrument-id-allocation-artifact-review.yml"
        ).read_text()
        self.assertIn("actions: read", text)
        self.assertIn("contents: read", text)
        self.assertIn("persist-credentials: false", text)
        self.assertIn(
            "ppi-stable-instrument-id-allocation-pilot-${SOURCE_RUN_ID}", text
        )
        self.assertNotIn("secrets.", text)
        self.assertNotIn("ai-signal-engine", text)

    def test_valid_success_artifact_passes(self):
        result = reviewer.review_artifact(
            artifact_root=self.artifact,
            source_run_json=self.run_json,
            source_run_id="31",
            source_run_attempt="1",
            contract_path=self.source_contract,
        )
        self.assertTrue(result["gate_passed"])
        self.assertEqual(result["allocation_counts"]["allocated"], 300)
        self.assertFalse(result["authority"]["universe_snapshot_assembly"])

    def test_exact_blocked_artifact_is_preserved(self):
        for path in list(self.artifact.iterdir()):
            path.unlink()
        self._write_json(
            self.artifact / "blocked.json",
            {
                "contract_id": reviewer.SOURCE_CONTRACT_ID,
                "status": "blocked",
                "reason": "upstream held",
                "stable_instrument_ids_allocated": 0,
                "private_access": False,
                "screening": False,
                "deep_evidence_collection": False,
                "registry_mutation": False,
            },
        )
        (self.artifact / "report.md").write_text("# Blocked\n")
        result = reviewer.review_artifact(
            artifact_root=self.artifact,
            source_run_json=self.run_json,
            source_run_id="31",
            source_run_attempt="1",
            contract_path=self.source_contract,
        )
        self.assertFalse(result["gate_passed"])
        self.assertEqual(result["allocation_counts"]["allocated"], 0)

    def test_tampered_snapshot_fails(self):
        path = self.artifact / "instrument-id-allocation-500.jsonl"
        path.write_bytes(path.read_bytes() + b"{}\n")
        with self.assertRaises(reviewer.ReviewError):
            reviewer.validate_success(
                self.artifact, self.source_contract, "31", "1"
            )

    def test_wrong_derived_instrument_id_fails(self):
        records = [
            json.loads(line)
            for line in (
                self.artifact / "instrument-id-allocation-500.jsonl"
            ).read_text().splitlines()
        ]
        records[0]["instrument_id"] = "ppi-us-equity-" + "f" * 24
        self._rewrite_snapshot(records)
        with self.assertRaises(reviewer.ReviewError):
            reviewer.validate_success(
                self.artifact, self.source_contract, "31", "1"
            )

    def test_ambiguous_record_cannot_receive_id(self):
        records = [
            json.loads(line)
            for line in (
                self.artifact / "instrument-id-allocation-500.jsonl"
            ).read_text().splitlines()
        ]
        records[300]["instrument_id"] = allocator.stable_instrument_id(
            "BBG999999999"
        )
        self._rewrite_snapshot(records)
        with self.assertRaises(reviewer.ReviewError):
            reviewer.validate_success(
                self.artifact, self.source_contract, "31", "1"
            )

    def test_duplicate_instrument_id_fails(self):
        records = [
            json.loads(line)
            for line in (
                self.artifact / "instrument-id-allocation-500.jsonl"
            ).read_text().splitlines()
        ]
        for key in (
            "instrument_id",
            "identity_key_value",
            "figi",
            "identity_input_sha256",
        ):
            records[1][key] = records[0][key]
        self._rewrite_snapshot(records)
        with self.assertRaises(reviewer.ReviewError):
            reviewer.validate_success(
                self.artifact, self.source_contract, "31", "1"
            )

    def test_wrong_source_run_identity_fails(self):
        value = json.loads(self.run_json.read_text())
        value["name"] = "Wrong workflow"
        self._write_json(self.run_json, value)
        with self.assertRaises(reviewer.ReviewError):
            reviewer.review_artifact(
                artifact_root=self.artifact,
                source_run_json=self.run_json,
                source_run_id="31",
                source_run_attempt="1",
                contract_path=self.source_contract,
            )

    def test_review_output_is_exactly_two_safe_files(self):
        value = reviewer.review_artifact(
            artifact_root=self.artifact,
            source_run_json=self.run_json,
            source_run_id="31",
            source_run_attempt="1",
            contract_path=self.source_contract,
        )
        reviewer.write_review(self.output, value)
        self.assertEqual(
            reviewer.files_under(self.output), {"review.json", "review.md"}
        )
        receipt = json.loads((self.output / "review.json").read_text())
        self.assertTrue(receipt["gate_passed"])
        self.assertFalse(receipt["authority"]["registry_mutation"])


if __name__ == "__main__":
    unittest.main()
