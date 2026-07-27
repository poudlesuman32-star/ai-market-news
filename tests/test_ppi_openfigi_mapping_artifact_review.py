from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts import review_openfigi_mapping_artifact as r


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.artifact = self.root / "artifact"
        self.artifact.mkdir()
        self.contract = self.root / "contract.json"
        self.contract.write_text('{"contract_id":"PPI-OPENFIGI-MAPPING-PILOT-001-R1"}\n')
        self.run = self.root / "run.json"
        self.run.write_text(json.dumps({
            "id": 123,
            "run_attempt": 1,
            "name": r.SOURCE_WORKFLOW_NAME,
            "repository": {"full_name": r.EXPECTED_REPOSITORY},
            "head_branch": "main",
            "status": "completed",
            "conclusion": "success",
        }))

    def tearDown(self):
        self.tmp.cleanup()

    def match(self, i: int, suffix: int = 0) -> dict:
        figi = f"BBG{i:08d}{suffix}"
        return {
            "figi": figi,
            "composite_figi": None,
            "share_class_figi": None,
            "ticker": f"T{i:04d}",
            "name": f"Issuer {i}",
            "exchange_code": "US",
            "market_sector": "Equity",
            "security_type": "Common Stock",
            "security_type2": "Common Stock",
            "security_description": f"T{i:04d}",
        }

    def record(self, i: int) -> dict:
        if i == 498:
            status = "ambiguous"
            matches = [self.match(i, 0), self.match(i, 1)]
            reason = "multiple_eligible_figi_matches"
        elif i == 499:
            status, matches, reason = "unmatched", [], "no_identifier_found"
        else:
            status, matches, reason = "exact", [self.match(i)], None
        return {
            "candidate_id": f"ppi-sec-seed-{i:024x}",
            "cik": f"{i:010d}",
            "ticker": f"T{i:04d}",
            "exchange": ("NYSE", "NASDAQ", "NYSE_AMERICAN")[i % 3],
            "source_row_sha256": r.digest(f"source-{i}".encode()),
            "mapping_status": status,
            "match_count": len(matches),
            "matches": matches,
            "request_sha256": r.digest(f"request-{i}".encode()),
            "response_sha256": r.digest(f"response-{i}".encode()),
            "reason": reason,
        }

    def build_success(self):
        records = [self.record(i) for i in range(500)]
        snapshot = b"".join(r.canon(record) for record in records)
        (self.artifact / "openfigi-mapping-500.jsonl").write_bytes(snapshot)
        counts = {
            state: sum(record["mapping_status"] == state for record in records)
            for state in ("exact", "ambiguous", "unmatched")
        }
        core = {
            "schema_version": "1.0.0",
            "contract_id": r.SOURCE_CONTRACT_ID,
            "generated_at_utc": "2026-07-27T00:00:00Z",
            "endpoint": r.ENDPOINT,
            "authentication_mode": "unauthenticated_free_tier",
            "api_key_used": False,
            "review_run_id": 11,
            "review_run_attempt": 1,
            "source_run_id": 10,
            "source_run_attempt": 1,
            "source_snapshot_sha256": r.digest(b"source-snapshot"),
            "candidate_count": 500,
            "jobs_per_request": 10,
            "request_count": 50,
            "mapping_counts": counts,
            "mapping_snapshot_sha256": r.digest(snapshot),
            "normalized_response_digest_sha256": r.digest(
                r.canon([record["response_sha256"] for record in records])
            ),
            "raw_openfigi_responses_retained": False,
        }
        manifest = {**core, "manifest_core_sha256": r.digest(r.canon(core))}
        (self.artifact / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n"
        )
        receipt = {
            "schema_version": "1.0.0",
            "contract_id": r.SOURCE_CONTRACT_ID,
            "contract_sha256": r.digest(self.contract.read_bytes()),
            "repository": r.EXPECTED_REPOSITORY,
            "run_id": "123",
            "run_attempt": "1",
            "event_name": "workflow_run",
            "head_sha": "a" * 40,
            "generated_at_utc": "2026-07-27T00:00:00Z",
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
        }
        (self.artifact / "receipt.json").write_text(
            json.dumps(receipt, indent=2, sort_keys=True) + "\n"
        )
        (self.artifact / "report.md").write_text(
            "# PPI OpenFIGI 500-candidate mapping pilot\n\n"
            f"- Status: success\n- Candidates: 500\n- Requests: 50\n- Exact: {counts['exact']}\n"
            f"- Ambiguous: {counts['ambiguous']}\n- Unmatched: {counts['unmatched']}\n"
        )

    def review(self):
        return r.review_artifact(
            artifact_root=self.artifact,
            source_run_json=self.run,
            source_run_id="123",
            source_run_attempt="1",
            contract_path=self.contract,
        )

    def test_contract_authority_is_narrow(self):
        contract = json.loads(
            Path("contracts/PPI-OPENFIGI-MAPPING-ARTIFACT-REVIEW-001-R1.json").read_text()
        )
        self.assertEqual(contract["authorized_actions"], [])
        self.assertTrue(all(value is False for value in contract["authority"].values()))
        self.assertEqual(contract["artifact_modes"]["success"]["candidate_count"], 500)
        self.assertEqual(contract["artifact_modes"]["success"]["exact_request_count"], 50)

    def test_workflow_is_read_only_and_source_bound(self):
        workflow = Path(
            ".github/workflows/ppi-openfigi-mapping-artifact-review.yml"
        ).read_text()
        self.assertIn("actions: read", workflow)
        self.assertIn("contents: read", workflow)
        self.assertIn(
            "ppi-openfigi-mapping-pilot-${SOURCE_RUN_ID}-${SOURCE_RUN_ATTEMPT}",
            workflow,
        )
        self.assertIn("persist-credentials: false", workflow)
        self.assertNotIn("secrets.", workflow)
        self.assertNotIn("ai-signal-engine", workflow)
        self.assertNotIn("registry", workflow.lower())

    def test_valid_success(self):
        self.build_success()
        value = self.review()
        self.assertTrue(value["gate_passed"])
        self.assertEqual(value["candidate_count"], 500)
        self.assertEqual(value["request_count"], 50)
        self.assertEqual(
            value["mapping_counts"],
            {"exact": 498, "ambiguous": 1, "unmatched": 1},
        )
        self.assertFalse(value["authority"]["stable_instrument_id_allocation"])

    def test_blocked_artifact(self):
        (self.artifact / "blocked.json").write_text(json.dumps({
            "contract_id": r.SOURCE_CONTRACT_ID,
            "status": "blocked",
            "reason": "SEC review not passed",
            "openfigi_requests_performed": 0,
            "private_access": False,
            "deep_evidence_collection": False,
            "registry_mutation": False,
        }))
        (self.artifact / "report.md").write_text("blocked\n")
        value = self.review()
        self.assertFalse(value["gate_passed"])
        self.assertEqual(value["request_count"], 0)

    def test_tampered_snapshot_rejected(self):
        self.build_success()
        path = self.artifact / "openfigi-mapping-500.jsonl"
        path.write_bytes(
            path.read_bytes().replace(b'"ticker":"T0000"', b'"ticker":"X0000"', 1)
        )
        with self.assertRaises(r.ReviewError):
            self.review()

    def test_wrong_request_count_rejected(self):
        self.build_success()
        path = self.artifact / "manifest.json"
        value = json.loads(path.read_text())
        value["request_count"] = 49
        path.write_text(json.dumps(value))
        with self.assertRaises(r.ReviewError):
            self.review()

    def test_inconsistent_status_rejected(self):
        self.build_success()
        path = self.artifact / "openfigi-mapping-500.jsonl"
        lines = path.read_text().splitlines()
        value = json.loads(lines[0])
        value["mapping_status"] = "unmatched"
        lines[0] = json.dumps(value, sort_keys=True, separators=(",", ":"))
        path.write_text("\n".join(lines) + "\n")
        with self.assertRaises(r.ReviewError):
            self.review()

    def test_unexpected_path_rejected(self):
        self.build_success()
        (self.artifact / "raw-openfigi.json").write_text("{}")
        with self.assertRaises(r.ReviewError):
            self.review()

    def test_wrong_source_run_rejected(self):
        self.build_success()
        run = json.loads(self.run.read_text())
        run["name"] = "Different workflow"
        self.run.write_text(json.dumps(run))
        with self.assertRaises(r.ReviewError):
            self.review()

    def test_write_review_exact_paths(self):
        self.build_success()
        value = self.review()
        output = self.root / "review"
        r.write_review(output, value)
        self.assertEqual(r.files_under(output), {"review.json", "review.md"})
        receipt = json.loads((output / "review.json").read_text())
        self.assertTrue(r.valid_hex(receipt["review_core_sha256"]))


if __name__ == "__main__":
    unittest.main()
