from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts/assemble_immutable_universe_snapshot.py"
CONTRACT_PATH = ROOT / "contracts/PPI-IMMUTABLE-UNIVERSE-SNAPSHOT-PILOT-001-R1.json"
WORKFLOW_PATH = ROOT / ".github/workflows/ppi-immutable-universe-snapshot-pilot.yml"

spec = importlib.util.spec_from_file_location("snapshot", SCRIPT_PATH)
assert spec and spec.loader
snapshot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(snapshot)


def stable_id(index: int) -> str:
    return f"ppi-us-equity-{index:024x}"


def figi(index: int) -> str:
    return f"BBG{index:09d}"


def allocation_record(index: int, status: str) -> dict:
    candidate = f"ppi-sec-seed-{index:024x}"
    base = {
        "candidate_id": candidate,
        "cik": f"{index + 1:010d}",
        "ticker": f"T{index}",
        "exchange": ["NYSE", "NASDAQ", "NYSE_AMERICAN"][index % 3],
        "source_row_sha256": "a" * 64,
        "mapping_status": "exact" if status == "allocated" else status.removeprefix("deferred_"),
        "mapping_record_sha256": "b" * 64,
        "allocation_status": status,
    }
    if status == "allocated":
        value = figi(index)
        return {
            **base,
            "instrument_id": stable_id(index),
            "identity_key_type": "FIGI",
            "identity_key_value": value,
            "figi": value,
            "composite_figi": None,
            "share_class_figi": None,
            "identity_input_sha256": "c" * 64,
        }
    return {
        **base,
        "instrument_id": None,
        "identity_key_type": None,
        "identity_key_value": None,
        "figi": None,
        "composite_figi": None,
        "share_class_figi": None,
        "identity_input_sha256": None,
    }


def make_source(root: Path) -> tuple[list[dict], dict]:
    records = []
    for index in range(500):
        status = "allocated" if index < 420 else "deferred_ambiguous" if index < 450 else "deferred_unmatched"
        records.append(allocation_record(index, status))
    records.sort(key=lambda item: item["candidate_id"])
    payload = b"".join(snapshot.canon(record) for record in records)
    counts = {
        state: sum(record["allocation_status"] == state for record in records)
        for state in snapshot.ALLOCATION_STATES
    }
    manifest_core = {
        "schema_version": "1.0.0",
        "contract_id": snapshot.SOURCE_CONTRACT_ID,
        "generated_at_utc": "2026-07-28T00:00:00Z",
        "algorithm": "sha256_figi_namespace_v1",
        "instrument_id_prefix": "ppi-us-equity-",
        "review_run_id": 10,
        "review_run_attempt": 1,
        "source_run_id": 9,
        "source_run_attempt": 1,
        "source_snapshot_sha256": "d" * 64,
        "mapping_snapshot_sha256": "e" * 64,
        "candidate_count": 500,
        "mapping_counts": {"exact": 420, "ambiguous": 30, "unmatched": 50},
        "allocation_counts": counts,
        "allocation_snapshot_sha256": snapshot.digest(payload),
        "ambiguous_and_unmatched_preserved": True,
        "network_requests_performed": 0,
    }
    manifest = {
        **manifest_core,
        "manifest_core_sha256": snapshot.digest(snapshot.canon(manifest_core)),
    }
    receipt = {
        "contract_id": snapshot.SOURCE_CONTRACT_ID,
        "run_id": "20",
        "run_attempt": "1",
        "allocation_snapshot_sha256": manifest["allocation_snapshot_sha256"],
        "network_requests_performed": 0,
        "private_access": False,
        "screening": False,
        "deep_evidence_collection": False,
        "registry_mutation": False,
    }
    root.mkdir()
    (root / "instrument-id-allocation-500.jsonl").write_bytes(payload)
    (root / "manifest.json").write_text(json.dumps(manifest) + "\n")
    (root / "receipt.json").write_text(json.dumps(receipt) + "\n")
    (root / "report.md").write_text("# report\n")
    return records, manifest


def make_review(root: Path, source_root: Path, manifest: dict, passed: bool = True) -> dict:
    value = {
        "schema_version": "1.0.0",
        "review_contract_id": snapshot.REVIEW_CONTRACT_ID,
        "source_contract_id": snapshot.SOURCE_CONTRACT_ID,
        "source_repository": snapshot.EXPECTED_REPOSITORY,
        "source_run_id": 20,
        "source_run_attempt": 1,
        "reviewed_at_utc": "2026-07-28T00:00:00Z",
        "artifact_mode": "success" if passed else "blocked",
        "gate_passed": passed,
        "candidate_count": 500 if passed else 0,
        "allocation_counts": (
            manifest["allocation_counts"]
            if passed
            else {"allocated": 0, "deferred_ambiguous": 0, "deferred_unmatched": 0}
        ),
        "mapping_counts": {"exact": 420, "ambiguous": 30, "unmatched": 50},
        "source_snapshot_sha256": manifest["source_snapshot_sha256"],
        "mapping_snapshot_sha256": manifest["mapping_snapshot_sha256"],
        "allocation_snapshot_sha256": manifest["allocation_snapshot_sha256"],
        "manifest_core_sha256": manifest["manifest_core_sha256"],
        "artifact_file_sha256": {
            path: snapshot.digest((source_root / path).read_bytes())
            for path in snapshot.SOURCE_PATHS
        },
        "authority": {
            "universe_snapshot_assembly": False,
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
    if not passed:
        value["blocked_reason"] = "held"
    output = {**value, "review_core_sha256": snapshot.digest(snapshot.canon(value))}
    root.mkdir()
    (root / "review.json").write_text(json.dumps(output) + "\n")
    (root / "review.md").write_text("# review\n")
    return output


def make_run(path: Path, run_id: int = 30) -> None:
    path.write_text(
        json.dumps(
            {
                "id": run_id,
                "run_attempt": 1,
                "name": snapshot.REVIEW_WORKFLOW_NAME,
                "repository": {"full_name": snapshot.EXPECTED_REPOSITORY},
                "head_branch": "main",
                "status": "completed",
                "conclusion": "success",
            }
        )
        + "\n"
    )


class ImmutableUniverseSnapshotTests(unittest.TestCase):
    def test_contract_is_public_only_and_snapshot_scoped(self) -> None:
        value = json.loads(CONTRACT_PATH.read_text())
        self.assertTrue(value["authority"]["universe_snapshot_assembly"])
        self.assertFalse(value["authority"]["network_access"])
        for key in (
            "screening",
            "deep_evidence_collection",
            "private_access",
            "private_dispatch",
            "billing_budget_mutation",
            "registry_mutation",
            "production",
            "publication",
            "trading",
        ):
            self.assertFalse(value["authority"][key], key)

    def test_assembly_splits_allocated_and_deferred_without_guessing(self) -> None:
        records = [
            allocation_record(0, "allocated"),
            allocation_record(1, "deferred_ambiguous"),
            allocation_record(2, "deferred_unmatched"),
        ] + [allocation_record(index, "allocated") for index in range(3, 500)]
        instruments, deferred = snapshot.assemble_records(records)
        self.assertEqual(len(instruments), 498)
        self.assertEqual(len(deferred), 2)
        self.assertTrue(all(item["instrument_id"] for item in instruments))
        self.assertEqual(
            {item["disposition"] for item in deferred},
            {"deferred_ambiguous", "deferred_unmatched"},
        )

    def test_execute_snapshot_produces_exact_five_path_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            _, manifest = make_source(source)
            review = root / "review"
            make_review(review, source, manifest)
            run_json = root / "run.json"
            make_run(run_json)
            output = root / "output"
            result = snapshot.execute_snapshot(
                review_root=review,
                review_run_json=run_json,
                review_run_id="30",
                review_run_attempt="1",
                source_root=source,
                output_root=output,
                contract_path=CONTRACT_PATH,
            )
            self.assertEqual(result["instrument_count"], 420)
            self.assertEqual(result["deferred_count"], 80)
            self.assertEqual(snapshot.files_under(output), snapshot.SUCCESS_PATHS)
            manifest_out = json.loads((output / "manifest.json").read_text())
            self.assertEqual(manifest_out["candidate_count"], 500)
            self.assertEqual(manifest_out["instrument_count"], 420)
            self.assertIsNone(manifest_out["previous_snapshot_sha256"])

    def test_snapshot_is_deterministic_for_same_records(self) -> None:
        records = [
            allocation_record(index, "allocated" if index < 490 else "deferred_unmatched")
            for index in range(500)
        ]
        first = snapshot.assemble_records(records)
        second = snapshot.assemble_records(list(reversed(records)))
        self.assertEqual(first, second)

    def test_duplicate_allocated_id_fails_closed(self) -> None:
        records = [allocation_record(index, "allocated") for index in range(500)]
        records[1]["instrument_id"] = records[0]["instrument_id"]
        with self.assertRaises(snapshot.SnapshotError):
            snapshot.assemble_records(records)

    def test_blocked_review_produces_zero_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            _, manifest = make_source(source)
            review = root / "review"
            make_review(review, source, manifest, passed=False)
            run_json = root / "run.json"
            make_run(run_json)
            output = root / "output"
            result = snapshot.preflight(
                review_root=review,
                review_run_json=run_json,
                review_run_id="30",
                review_run_attempt="1",
                output_root=output,
                github_output=None,
            )
            self.assertFalse(result["gate_passed"])
            self.assertEqual(snapshot.files_under(output), snapshot.BLOCKED_PATHS)

    def test_tampered_allocation_artifact_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            _, manifest = make_source(source)
            review = root / "review"
            review_value = make_review(review, source, manifest)
            with (source / "report.md").open("a") as handle:
                handle.write("tampered")
            with self.assertRaises(snapshot.SnapshotError):
                snapshot.validate_allocation_artifact(source, review_value)

    def test_workflow_is_read_only_and_gate_bound(self) -> None:
        text = WORKFLOW_PATH.read_text()
        self.assertIn("PPI stable instrument ID allocation artifact review", text)
        self.assertIn("steps.preflight.outputs.gate_passed == 'true'", text)
        self.assertIn("permissions:\n  contents: read", text)
        self.assertIn("actions: read", text)
        self.assertIn("persist-credentials: false", text)
        for forbidden in (
            "secrets.",
            "contents: write",
            "issues: write",
            "pull-requests: write",
            "musksuman3/ai-signal-engine",
            "ppi-data-acquisition",
        ):
            self.assertNotIn(forbidden, text)


if __name__ == "__main__":
    unittest.main()
