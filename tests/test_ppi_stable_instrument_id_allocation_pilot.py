from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "allocator", ROOT / "scripts" / "allocate_stable_instrument_ids.py"
)
allocator = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(allocator)


class StableInstrumentIdAllocationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.review_root = self.base / "review"
        self.source_root = self.base / "source"
        self.output_root = self.base / "output"
        self.review_run_json = self.base / "review-run.json"
        self.contract = ROOT / "contracts" / "PPI-STABLE-INSTRUMENT-ID-ALLOCATION-PILOT-001-R1.json"
        self.review_root.mkdir()
        self.source_root.mkdir()
        self._build_success_fixtures()

    def tearDown(self):
        self.temp.cleanup()

    @staticmethod
    def _figi(index: int, suffix: int = 0) -> str:
        return f"BBG{index * 3 + suffix + 1:09d}"

    @staticmethod
    def _candidate_id(index: int) -> str:
        return f"ppi-sec-seed-{index:024x}"

    def _match(self, index: int, suffix: int = 0) -> dict:
        return {
            "figi": self._figi(index, suffix),
            "composite_figi": self._figi(index, suffix + 700),
            "share_class_figi": self._figi(index, suffix + 1400),
            "ticker": f"T{index:04d}",
            "name": f"Issuer {index}",
            "exchange_code": "US",
            "market_sector": "Equity",
            "security_type": "Common Stock",
            "security_type2": "Common Stock",
            "security_description": f"T{index:04d}",
        }

    def _mapping_record(self, index: int) -> dict:
        if index < 300:
            status, matches, reason = "exact", [self._match(index)], None
        elif index < 400:
            status = "ambiguous"
            matches = sorted(
                [self._match(index, 0), self._match(index, 1)],
                key=lambda item: item["figi"],
            )
            reason = "multiple_eligible_figi_matches"
        else:
            status, matches, reason = "unmatched", [], "no_identifier_found"
        return {
            "candidate_id": self._candidate_id(index),
            "cik": f"{index + 1:010d}",
            "ticker": f"T{index:04d}",
            "exchange": ["NYSE", "NASDAQ", "NYSE_AMERICAN"][index % 3],
            "source_row_sha256": allocator.digest(f"row-{index}".encode()),
            "mapping_status": status,
            "match_count": len(matches),
            "matches": matches,
            "request_sha256": allocator.digest(f"request-{index}".encode()),
            "response_sha256": allocator.digest(f"response-{index}".encode()),
            "reason": reason,
        }

    @staticmethod
    def _write_json(path: Path, value: dict) -> None:
        path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def _build_success_fixtures(self) -> None:
        records = [self._mapping_record(index) for index in range(500)]
        snapshot = b"".join(allocator.canon(record) for record in records)
        (self.source_root / "openfigi-mapping-500.jsonl").write_bytes(snapshot)
        counts = {
            state: sum(record["mapping_status"] == state for record in records)
            for state in allocator.STATUSES
        }
        manifest_core = {
            "schema_version": "1.0.0",
            "contract_id": allocator.SOURCE_CONTRACT_ID,
            "endpoint": "https://api.openfigi.com/v3/mapping",
            "authentication_mode": "unauthenticated_free_tier",
            "api_key_used": False,
            "review_run_id": 12,
            "review_run_attempt": 1,
            "source_run_id": 10,
            "source_run_attempt": 1,
            "source_snapshot_sha256": allocator.digest(b"sec-snapshot"),
            "candidate_count": 500,
            "jobs_per_request": 10,
            "request_count": 50,
            "mapping_counts": counts,
            "mapping_snapshot_sha256": allocator.digest(snapshot),
            "normalized_response_digest_sha256": allocator.digest(
                allocator.canon([record["response_sha256"] for record in records])
            ),
            "raw_openfigi_responses_retained": False,
            "generated_at_utc": "2026-07-27T00:00:00Z",
        }
        manifest = {
            **manifest_core,
            "manifest_core_sha256": allocator.digest(allocator.canon(manifest_core)),
        }
        self._write_json(self.source_root / "manifest.json", manifest)
        self._write_json(
            self.source_root / "receipt.json",
            {
                "schema_version": "1.0.0",
                "contract_id": allocator.SOURCE_CONTRACT_ID,
                "repository": allocator.EXPECTED_REPOSITORY,
                "run_id": "10",
                "run_attempt": "1",
                "mapping_snapshot_sha256": manifest["mapping_snapshot_sha256"],
                "manifest_core_sha256": manifest["manifest_core_sha256"],
                "source_snapshot_sha256": manifest["source_snapshot_sha256"],
                "openfigi_requests_performed": 50,
                "api_key_used": False,
                "raw_openfigi_responses_retained": False,
                "private_access": False,
                "screening": False,
                "deep_evidence_collection": False,
                "private_dispatch": False,
                "billing_budget_mutation": False,
                "registry_mutation": False,
                "production": False,
                "publication": False,
                "trading": False,
                "authorized_actions": ["openfigi_mapping_public_pilot"],
            },
        )
        (self.source_root / "report.md").write_text(
            "# Mapping\n\n- Status: success\n- Candidates: 500\n- Requests: 50\n",
            encoding="utf-8",
        )
        artifact_hashes = {
            path: allocator.digest((self.source_root / path).read_bytes())
            for path in sorted(allocator.SOURCE_PATHS)
        }
        review_core = {
            "schema_version": "1.0.0",
            "review_contract_id": allocator.REVIEW_CONTRACT_ID,
            "source_contract_id": allocator.SOURCE_CONTRACT_ID,
            "source_repository": allocator.EXPECTED_REPOSITORY,
            "source_run_id": 10,
            "source_run_attempt": 1,
            "reviewed_at_utc": "2026-07-27T00:01:00Z",
            "source_run_checks": {"success": True},
            "artifact_mode": "success",
            "gate_passed": True,
            "candidate_count": 500,
            "request_count": 50,
            "mapping_counts": counts,
            "source_snapshot_sha256": manifest["source_snapshot_sha256"],
            "mapping_snapshot_sha256": manifest["mapping_snapshot_sha256"],
            "manifest_core_sha256": manifest["manifest_core_sha256"],
            "normalized_response_digest_sha256": manifest["normalized_response_digest_sha256"],
            "artifact_file_sha256": artifact_hashes,
            "checks": {"all": True},
            "authority": {
                "stable_instrument_id_allocation": False,
                "screening": False,
                "deep_evidence_collection": False,
                "private_access": False,
                "private_dispatch": False,
                "billing_budget_mutation": False,
                "registry_mutation": False,
                "production": False,
                "publication": False,
                "trading": False,
            },
        }
        review = {
            **review_core,
            "review_core_sha256": allocator.digest(allocator.canon(review_core)),
        }
        self._write_json(self.review_root / "review.json", review)
        (self.review_root / "review.md").write_text("# Review\n", encoding="utf-8")
        self._write_json(
            self.review_run_json,
            {
                "id": 20,
                "run_attempt": 1,
                "name": allocator.REVIEW_WORKFLOW_NAME,
                "repository": {"full_name": allocator.EXPECTED_REPOSITORY},
                "head_branch": "main",
                "status": "completed",
                "conclusion": "success",
            },
        )

    def test_contract_has_only_public_allocation_authority(self):
        contract = json.loads(self.contract.read_text())
        self.assertEqual(
            contract["authorized_actions"],
            ["stable_instrument_id_allocation_public_pilot"],
        )
        self.assertTrue(contract["authority"]["stable_instrument_id_allocation"])
        for key in (
            "screening", "deep_evidence_collection", "private_access",
            "private_dispatch", "billing_budget_mutation", "registry_mutation",
            "production", "publication", "trading",
        ):
            self.assertFalse(contract["authority"][key])

    def test_workflow_is_read_only_gate_bound_and_network_free(self):
        text = (ROOT / ".github/workflows/ppi-stable-instrument-id-allocation-pilot.yml").read_text()
        self.assertIn("actions: read", text)
        self.assertIn("contents: read", text)
        self.assertIn("persist-credentials: false", text)
        self.assertIn("steps.preflight.outputs.gate_passed == 'true'", text)
        self.assertNotIn("secrets.", text)
        self.assertNotIn("curl ", text)
        self.assertNotIn("api.openfigi.com", text)
        self.assertNotIn("ai-signal-engine", text)

    def test_blocked_review_allocates_zero_ids(self):
        review = json.loads((self.review_root / "review.json").read_text())
        core = {key: value for key, value in review.items() if key != "review_core_sha256"}
        core.update({
            "artifact_mode": "blocked",
            "gate_passed": False,
            "candidate_count": 0,
            "request_count": 0,
            "mapping_counts": {"exact": 0, "ambiguous": 0, "unmatched": 0},
            "blocked_reason": "upstream held",
        })
        for key in (
            "source_snapshot_sha256", "mapping_snapshot_sha256",
            "manifest_core_sha256", "normalized_response_digest_sha256",
            "artifact_file_sha256",
        ):
            core.pop(key, None)
        blocked = {
            **core,
            "review_core_sha256": allocator.digest(allocator.canon(core)),
        }
        self._write_json(self.review_root / "review.json", blocked)
        result = allocator.preflight(
            review_root=self.review_root,
            review_run_json=self.review_run_json,
            review_run_id="20",
            review_run_attempt="1",
            output_root=self.output_root,
            github_output=None,
        )
        self.assertFalse(result["gate_passed"])
        self.assertEqual(allocator.files_under(self.output_root), allocator.BLOCKED_PATHS)
        value = json.loads((self.output_root / "blocked.json").read_text())
        self.assertEqual(value["stable_instrument_ids_allocated"], 0)

    def test_allocation_is_deterministic_and_defers_non_exact(self):
        mappings = [self._mapping_record(index) for index in range(500)]
        first = allocator.allocate_records(mappings)
        second = allocator.allocate_records(mappings)
        self.assertEqual(first, second)
        counts = {
            state: sum(record["allocation_status"] == state for record in first)
            for state in ("allocated", "deferred_ambiguous", "deferred_unmatched")
        }
        self.assertEqual(
            counts,
            {"allocated": 300, "deferred_ambiguous": 100, "deferred_unmatched": 100},
        )
        self.assertTrue(all(record["instrument_id"] for record in first[:300]))
        self.assertTrue(all(record["instrument_id"] is None for record in first[300:]))

    def test_same_figi_always_produces_same_instrument_id(self):
        figi = "BBG000000001"
        value = allocator.stable_instrument_id(figi)
        self.assertEqual(value, allocator.stable_instrument_id(figi))
        self.assertRegex(value, allocator.INSTRUMENT_ID)

    def test_duplicate_exact_figi_fails_closed(self):
        mappings = [self._mapping_record(index) for index in range(500)]
        mappings[1]["matches"][0]["figi"] = mappings[0]["matches"][0]["figi"]
        with self.assertRaises(allocator.AllocationError):
            allocator.allocate_records(mappings)

    def test_exact_success_writes_four_safe_paths(self):
        result = allocator.execute_allocation(
            review_root=self.review_root,
            review_run_json=self.review_run_json,
            review_run_id="20",
            review_run_attempt="1",
            source_root=self.source_root,
            output_root=self.output_root,
            contract_path=self.contract,
        )
        self.assertEqual(result, {"candidate_count": 500, "allocated_count": 300})
        self.assertEqual(allocator.files_under(self.output_root), allocator.SUCCESS_PATHS)
        manifest = json.loads((self.output_root / "manifest.json").read_text())
        self.assertEqual(manifest["network_requests_performed"], 0)
        self.assertTrue(manifest["ambiguous_and_unmatched_preserved"])

    def test_tampered_mapping_artifact_fails(self):
        path = self.source_root / "report.md"
        path.write_text(path.read_text() + "tampered\n")
        review = allocator.validate_review(self.review_root, self.review_run_json, "20", "1")
        with self.assertRaises(allocator.AllocationError):
            allocator.validate_mapping_artifact(self.source_root, review)

    def test_wrong_review_workflow_identity_fails(self):
        value = json.loads(self.review_run_json.read_text())
        value["name"] = "Wrong workflow"
        self._write_json(self.review_run_json, value)
        with self.assertRaises(allocator.AllocationError):
            allocator.validate_review(self.review_root, self.review_run_json, "20", "1")

    def test_allocation_output_contains_no_registry_authority(self):
        allocator.execute_allocation(
            review_root=self.review_root,
            review_run_json=self.review_run_json,
            review_run_id="20",
            review_run_attempt="1",
            source_root=self.source_root,
            output_root=self.output_root,
            contract_path=self.contract,
        )
        receipt = json.loads((self.output_root / "receipt.json").read_text())
        self.assertEqual(
            receipt["authorized_actions"],
            ["stable_instrument_id_allocation_public_pilot"],
        )
        self.assertFalse(receipt["registry_mutation"])
        self.assertFalse(receipt["private_access"])
        self.assertEqual(receipt["network_requests_performed"], 0)


if __name__ == "__main__":
    unittest.main()
