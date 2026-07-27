from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).parents[1] / "scripts" / "map_openfigi_sec_pilot.py"
SPEC = importlib.util.spec_from_file_location("openfigi_pilot", MODULE_PATH)
m = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(m)
REPO_ROOT = Path(__file__).parents[1]


def candidate(index: int) -> dict:
    return {
        "candidate_id": f"ppi-sec-seed-{index:024x}",
        "cik": f"{index:010d}",
        "company_name": f"Company {index}",
        "ticker": f"T{index:04d}",
        "exchange": ("NYSE", "NASDAQ", "NYSE_AMERICAN")[index % 3],
        "identity_status": "provisional_sec_seed",
        "classification_status": "unresolved",
        "source_id": "sec_company_tickers_exchange",
        "source_row_sha256": m.digest(m.canon({"index": index})),
    }


def make_source(root: Path, source_run_id: int = 1234, source_attempt: int = 1):
    root.mkdir(parents=True)
    candidates = [candidate(index) for index in range(1, 501)]
    snapshot = b"".join(m.canon(item) for item in candidates)
    snapshot_hash = m.digest(snapshot)
    manifest_core = {
        "contract_id": m.SOURCE_CONTRACT_ID,
        "snapshot_sha256": snapshot_hash,
        "candidate_count": 500,
    }
    manifest = {**manifest_core, "manifest_core_sha256": m.digest(m.canon(manifest_core))}
    receipt = {
        "contract_id": m.SOURCE_CONTRACT_ID,
        "snapshot_sha256": snapshot_hash,
        "run_id": str(source_run_id),
        "run_attempt": str(source_attempt),
        "raw_payload_retained": False,
        "private_access": False,
        "deep_evidence": False,
        "registry_mutation": False,
    }
    (root / "sec-universe-pilot-500.jsonl").write_bytes(snapshot)
    (root / "manifest.json").write_text(json.dumps(manifest, sort_keys=True) + "\n")
    (root / "receipt.json").write_text(json.dumps(receipt, sort_keys=True) + "\n")
    (root / "report.md").write_text("# source\n")
    hashes = {p: m.digest((root / p).read_bytes()) for p in sorted(m.SOURCE_PATHS)}
    return candidates, {
        "snapshot_sha256": snapshot_hash,
        "manifest_core_sha256": manifest["manifest_core_sha256"],
        "artifact_file_sha256": hashes,
    }


def make_review(root: Path, source_info: dict, *, gate_passed: bool = True,
                review_run_id: int = 5678, review_attempt: int = 1,
                source_run_id: int = 1234, source_attempt: int = 1) -> Path:
    review_root = root / "review"
    review_root.mkdir(parents=True)
    value = {
        "schema_version": "1.0.0",
        "review_contract_id": m.REVIEW_CONTRACT_ID,
        "source_contract_id": m.SOURCE_CONTRACT_ID,
        "source_repository": m.EXPECTED_REPOSITORY,
        "source_run_id": source_run_id,
        "source_run_attempt": source_attempt,
        "reviewed_at_utc": "2026-07-27T00:00:00Z",
        "source_run_checks": {"success": True},
        "artifact_mode": "success" if gate_passed else "blocked",
        "gate_passed": gate_passed,
        "candidate_count": 500 if gate_passed else 0,
        "authority": {
            "openfigi_mapping": False,
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
    if gate_passed:
        value.update(source_info)
        value["exclusion_counts"] = {}
        value["checks"] = {"all": True}
    else:
        value["blocked_reason"] = "SEC user agent missing"
        value["checks"] = {"blocked": True}
    output = {**value, "review_core_sha256": m.digest(m.canon(value))}
    (review_root / "review.json").write_text(json.dumps(output, sort_keys=True) + "\n")
    (review_root / "review.md").write_text("# review\n")
    run = {
        "id": review_run_id,
        "run_attempt": review_attempt,
        "name": m.REVIEW_WORKFLOW_NAME,
        "repository": {"full_name": m.EXPECTED_REPOSITORY},
        "head_branch": "main",
        "status": "completed",
        "conclusion": "success",
    }
    run_path = root / "review-run.json"
    run_path.write_text(json.dumps(run))
    return run_path


class OpenFigiPilotTests(unittest.TestCase):
    def test_contract_has_narrow_authority(self):
        contract = json.loads((REPO_ROOT / "contracts/PPI-OPENFIGI-MAPPING-PILOT-001-R1.json").read_text())
        self.assertTrue(contract["authority"]["openfigi_mapping"])
        for key in ("screening", "deep_evidence_collection", "private_access", "private_dispatch",
                    "billing_budget_mutation", "registry_mutation", "production", "publication",
                    "broker", "orders", "trading", "mmm_raw_data", "r12"):
            self.assertFalse(contract["authority"][key])
        self.assertEqual(contract["authorized_actions"], ["openfigi_mapping_public_pilot"])
        self.assertFalse(contract["authentication"]["api_key_allowed"])

    def test_workflow_is_gate_bound_and_secret_free(self):
        text = (REPO_ROOT / ".github/workflows/ppi-openfigi-mapping-pilot.yml").read_text()
        self.assertIn("steps.preflight.outputs.gate_passed == 'true'", text)
        self.assertNotIn("secrets.", text)
        self.assertNotIn("ai-signal-engine", text)
        self.assertNotIn("X-OPENFIGI-APIKEY", text)
        self.assertIn("actions: read", text)
        self.assertIn("contents: read", text)

    def test_blocked_review_performs_zero_requests(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, source_info = make_source(root / "source")
            run_json = make_review(root, source_info, gate_passed=False)
            output = root / "output"
            values = m.preflight(
                review_root=root / "review", review_run_json=run_json,
                review_run_id="5678", review_run_attempt="1",
                output_root=output, github_output=None,
            )
            self.assertFalse(values["gate_passed"])
            self.assertEqual(m.files_under(output), m.BLOCKED_PATHS)
            blocked = json.loads((output / "blocked.json").read_text())
            self.assertEqual(blocked["openfigi_requests_performed"], 0)

    def test_passed_review_returns_exact_source_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, source_info = make_source(root / "source")
            run_json = make_review(root, source_info)
            values = m.preflight(
                review_root=root / "review", review_run_json=run_json,
                review_run_id="5678", review_run_attempt="1",
                output_root=root / "output", github_output=None,
            )
            self.assertTrue(values["gate_passed"])
            self.assertEqual(values["source_run_id"], 1234)
            self.assertFalse((root / "output").exists())

    def test_classifies_exact_ambiguous_and_unmatched(self):
        base = candidate(1)
        exact = m.classify_result(base, {"data": [{
            "figi": "BBG000000001", "ticker": base["ticker"],
            "marketSector": "Equity", "securityType2": "Common Stock",
        }]})
        self.assertEqual(exact["mapping_status"], "exact")
        ambiguous = m.classify_result(base, {"data": [
            {"figi": "BBG000000001", "ticker": base["ticker"], "marketSector": "Equity"},
            {"figi": "BBG000000002", "ticker": base["ticker"], "marketSector": "Equity"},
        ]})
        self.assertEqual(ambiguous["mapping_status"], "ambiguous")
        unmatched = m.classify_result(base, {"warning": "No identifier found."})
        self.assertEqual(unmatched["mapping_status"], "unmatched")

    def test_provider_error_fails_closed(self):
        with self.assertRaises(m.MappingError):
            m.classify_result(candidate(1), {"error": "Invalid request"})

    def test_source_tampering_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, source_info = make_source(root / "source")
            run_json = make_review(root, source_info)
            review = m.validate_review(root / "review", run_json, "5678", "1")
            (root / "source" / "report.md").write_text("tampered\n")
            with self.assertRaises(m.MappingError):
                m.validate_source_artifact(root / "source", review)

    def test_maps_500_candidates_in_50_requests(self):
        candidates = [candidate(index) for index in range(1, 501)]
        calls = []
        def fake_fetch(jobs):
            calls.append(jobs)
            return [{"data": [{
                "figi": f"BBG{int(job['idValue'][1:]):09d}",
                "ticker": job["idValue"], "marketSector": "Equity",
                "securityType2": "Common Stock",
            }]} for job in jobs]
        records, count = m.map_candidates(candidates, fetcher=fake_fetch, sleep=lambda _: None)
        self.assertEqual(count, 50)
        self.assertEqual(len(calls), 50)
        self.assertTrue(all(len(batch) == 10 for batch in calls))
        self.assertEqual(len(records), 500)
        self.assertTrue(all(record["mapping_status"] == "exact" for record in records))


if __name__ == "__main__":
    unittest.main()
