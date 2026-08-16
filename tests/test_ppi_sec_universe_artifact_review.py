from __future__ import annotations

import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "review_sec_universe_pilot_artifact.py"
SOURCE_CONTRACT = ROOT / "contracts/PPI-SEC-UNIVERSE-PILOT-001-R1.json"
REVIEW_CONTRACT = ROOT / "contracts/PPI-SEC-UNIVERSE-ARTIFACT-REVIEW-001-R1.json"
WORKFLOW = ROOT / ".github/workflows/ppi-sec-universe-artifact-review.yml"

spec = importlib.util.spec_from_file_location("review_module", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(module)


def canon(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode()


def digest(value):
    return hashlib.sha256(value).hexdigest()


class SecUniverseArtifactReviewTests(unittest.TestCase):
    def source_run(self):
        return {
            "id": 12345,
            "run_attempt": 1,
            "name": "SEC 500 pilot - workflow_dispatch - main",
            "path": module.SOURCE_WORKFLOW_PATH,
            "event": module.SOURCE_EVENT,
            "repository": {"full_name": module.EXPECTED_REPOSITORY},
            "head_branch": "main",
            "status": "completed",
            "conclusion": "success",
        }

    def candidate(self, index):
        seed = digest(f"candidate-{index}".encode())
        row = {
            "cik": str(index + 1).zfill(10),
            "company_name": f"Company {index}",
            "ticker": f"T{index}",
            "exchange": sorted(module.EXCHANGES)[index % 3],
        }
        return {
            "candidate_id": f"ppi-sec-seed-{seed[:24]}",
            **row,
            "identity_status": "provisional_sec_seed",
            "classification_status": "unresolved",
            "source_id": "sec_company_tickers_exchange",
            "source_row_sha256": digest(canon(row)),
        }

    def success_fixture(self, root):
        candidates = sorted((self.candidate(i) for i in range(500)), key=lambda v: v["candidate_id"])
        snapshot = b"".join(canon(v) for v in candidates)
        snapshot_hash = digest(snapshot)
        core = {
            "schema_version": "1.0.0",
            "contract_id": module.SOURCE_CONTRACT_ID,
            "snapshot_id": f"ppi-sec-universe-pilot-{snapshot_hash[:16]}",
            "generated_at_utc": "2026-07-26T00:00:00Z",
            "source_url": module.SOURCE_URL,
            "source_payload_sha256": "a" * 64,
            "source_bytes": 1000,
            "source_row_count": 1000,
            "normalized_eligible_count": 900,
            "candidate_count": 500,
            "candidate_limit": 500,
            "selection_algorithm": "sha256_rank_v1",
            "snapshot_sha256": snapshot_hash,
            "exclusion_counts": {"unsupported_exchange": 100},
            "source_http": {"status": 200, "content_type": "application/json", "content_encoding": None, "etag": None, "last_modified": None},
        }
        manifest = {**core, "manifest_core_sha256": digest(canon(core))}
        receipt = {
            "schema_version": "1.0.0",
            "contract_id": module.SOURCE_CONTRACT_ID,
            "contract_sha256": digest(SOURCE_CONTRACT.read_bytes()),
            "repository": module.EXPECTED_REPOSITORY,
            "run_id": "12345",
            "run_attempt": "1",
            "event_name": "workflow_dispatch",
            "head_sha": "b" * 40,
            "generated_at_utc": "2026-07-26T00:00:00Z",
            "source_payload_sha256": "a" * 64,
            "snapshot_sha256": snapshot_hash,
            "manifest_core_sha256": manifest["manifest_core_sha256"],
            "remote_fetch_performed": True,
            "request_attempts": 1,
            "raw_payload_retained": False,
            "private_access": False,
            "deep_evidence": False,
            "registry_mutation": False,
            "authorized_actions": [],
        }
        (root / "sec-universe-pilot-500.jsonl").write_bytes(snapshot)
        (root / "manifest.json").write_text(json.dumps(manifest))
        (root / "receipt.json").write_text(json.dumps(receipt))
        (root / "report.md").write_text("- Status: success\n- Candidate count: 500\n")

    def run_review(self, artifact, source=None):
        source_path = artifact.parent / "source-run.json"
        source_path.write_text(json.dumps(source or self.source_run()))
        return module.review_artifact(
            artifact_root=artifact,
            source_run_json=source_path,
            source_run_id="12345",
            source_run_attempt="1",
            contract_path=SOURCE_CONTRACT,
        )

    def test_contract_has_only_public_review_authority(self):
        value = json.loads(REVIEW_CONTRACT.read_text())
        self.assertTrue(value["authority"]["source_artifact_download"])
        self.assertTrue(value["authority"]["source_artifact_verification"])
        for key in ("openfigi_mapping", "screening", "deep_evidence_collection", "private_access",
                    "private_dispatch", "billing_budget_mutation", "registry_mutation",
                    "production", "publication", "trading"):
            self.assertFalse(value["authority"][key], key)

    def test_workflow_is_exact_public_review(self):
        text = WORKFLOW.read_text()
        for required in ("workflow_run:", "PPI SEC 500-instrument universe pilot", "actions: read",
                         "contents: read", 'gh run download "$SOURCE_RUN_ID"', "persist-credentials: false"):
            self.assertIn(required, text)
        for forbidden in ("secrets.", "ai-signal-engine", "openfigi.com", "registry_mutation: true"):
            self.assertNotIn(forbidden, text)

    def test_exact_success_artifact_passes_with_custom_run_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifact = Path(tmp) / "artifact"
            artifact.mkdir()
            self.success_fixture(artifact)
            review = self.run_review(artifact)
            self.assertTrue(review["gate_passed"])
            self.assertEqual(review["candidate_count"], 500)
            self.assertTrue(review["source_run_checks"]["workflow_path"])
            self.assertTrue(review["source_run_checks"]["event"])

    def test_exact_blocked_artifact_does_not_advance(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifact = Path(tmp) / "artifact"
            artifact.mkdir()
            blocked = {
                "contract_id": module.SOURCE_CONTRACT_ID,
                "status": "blocked",
                "reason": "missing user agent",
                "remote_fetch_performed": False,
                "private_access": False,
                "deep_evidence": False,
                "registry_mutation": False,
            }
            (artifact / "blocked.json").write_text(json.dumps(blocked))
            (artifact / "report.md").write_text("blocked")
            review = self.run_review(artifact)
            self.assertFalse(review["gate_passed"])
            self.assertEqual(review["artifact_mode"], "blocked")

    def test_unexpected_path_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifact = Path(tmp) / "artifact"
            artifact.mkdir()
            self.success_fixture(artifact)
            (artifact / "raw-sec.json").write_text("{}")
            with self.assertRaises(module.ReviewError):
                self.run_review(artifact)

    def test_tampered_snapshot_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifact = Path(tmp) / "artifact"
            artifact.mkdir()
            self.success_fixture(artifact)
            path = artifact / "sec-universe-pilot-500.jsonl"
            path.write_bytes(path.read_bytes().replace(b"Company 1", b"Tampered 1", 1))
            with self.assertRaises(module.ReviewError):
                self.run_review(artifact)

    def test_source_run_branch_mismatch_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifact = Path(tmp) / "artifact"
            artifact.mkdir()
            self.success_fixture(artifact)
            source = self.source_run()
            source["head_branch"] = "feature/unsafe"
            with self.assertRaises(module.ReviewError):
                self.run_review(artifact, source)

    def test_source_run_path_mismatch_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifact = Path(tmp) / "artifact"
            artifact.mkdir()
            self.success_fixture(artifact)
            source = self.source_run()
            source["path"] = ".github/workflows/other.yml"
            with self.assertRaises(module.ReviewError):
                self.run_review(artifact, source)

    def test_source_run_event_mismatch_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifact = Path(tmp) / "artifact"
            artifact.mkdir()
            self.success_fixture(artifact)
            source = self.source_run()
            source["event"] = "schedule"
            with self.assertRaises(module.ReviewError):
                self.run_review(artifact, source)


if __name__ == "__main__":
    unittest.main()
