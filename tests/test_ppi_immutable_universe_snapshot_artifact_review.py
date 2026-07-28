from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts/review_immutable_universe_snapshot.py"
CONTRACT_PATH = ROOT / "contracts/PPI-IMMUTABLE-UNIVERSE-SNAPSHOT-ARTIFACT-REVIEW-001-R1.json"
SOURCE_CONTRACT_PATH = ROOT / "contracts/PPI-IMMUTABLE-UNIVERSE-SNAPSHOT-PILOT-001-R1.json"
WORKFLOW_PATH = ROOT / ".github/workflows/ppi-immutable-universe-snapshot-artifact-review.yml"

spec = importlib.util.spec_from_file_location("reviewer", SCRIPT_PATH)
assert spec and spec.loader
reviewer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reviewer)

source_spec = importlib.util.spec_from_file_location(
    "source_tests", ROOT / "tests/test_ppi_immutable_universe_snapshot_pilot.py"
)
assert source_spec and source_spec.loader
source_tests = importlib.util.module_from_spec(source_spec)
source_spec.loader.exec_module(source_tests)


def make_success_artifact(root: Path) -> None:
    allocation = root / "allocation"
    _, manifest = source_tests.make_source(allocation)
    review = root / "allocation-review"
    source_tests.make_review(review, allocation, manifest)
    review_run = root / "allocation-review-run.json"
    source_tests.make_run(review_run, 30)
    artifact = root / "snapshot-artifact"
    old_env = {
        key: __import__("os").environ.get(key)
        for key in ("GITHUB_REPOSITORY", "GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT")
    }
    try:
        __import__("os").environ["GITHUB_REPOSITORY"] = reviewer.EXPECTED_REPOSITORY
        __import__("os").environ["GITHUB_RUN_ID"] = "40"
        __import__("os").environ["GITHUB_RUN_ATTEMPT"] = "1"
        reviewer.assembler.execute_snapshot(
            review_root=review,
            review_run_json=review_run,
            review_run_id="30",
            review_run_attempt="1",
            source_root=allocation,
            output_root=artifact,
            contract_path=SOURCE_CONTRACT_PATH,
        )
    finally:
        for key, value in old_env.items():
            if value is None:
                __import__("os").environ.pop(key, None)
            else:
                __import__("os").environ[key] = value


def make_run(path: Path, run_id: int = 40) -> None:
    path.write_text(
        json.dumps(
            {
                "id": run_id,
                "run_attempt": 1,
                "name": reviewer.SOURCE_WORKFLOW_NAME,
                "repository": {"full_name": reviewer.EXPECTED_REPOSITORY},
                "head_branch": "main",
                "status": "completed",
                "conclusion": "success",
            }
        )
        + "\n"
    )


class ImmutableUniverseSnapshotArtifactReviewTests(unittest.TestCase):
    def test_contract_has_no_downstream_authority(self) -> None:
        value = json.loads(CONTRACT_PATH.read_text())
        self.assertEqual(value["authorized_actions"], [])
        for key, enabled in value["authority"].items():
            self.assertFalse(enabled, key)

    def test_valid_snapshot_artifact_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_success_artifact(root)
            run_json = root / "run.json"
            make_run(run_json)
            value = reviewer.review_artifact(
                artifact_root=root / "snapshot-artifact",
                source_run_json=run_json,
                source_run_id="40",
                source_run_attempt="1",
                contract_path=SOURCE_CONTRACT_PATH,
            )
            self.assertTrue(value["gate_passed"])
            self.assertEqual(value["candidate_count"], 500)
            self.assertEqual(value["instrument_count"], 420)
            self.assertEqual(value["deferred_count"], 80)
            self.assertEqual(value["instrument_count"] + value["deferred_count"], 500)

    def test_blocked_artifact_is_reviewed_but_does_not_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            artifact = root / "artifact"
            artifact.mkdir()
            (artifact / "blocked.json").write_text(
                json.dumps(
                    {
                        "contract_id": reviewer.SOURCE_CONTRACT_ID,
                        "status": "blocked",
                        "universe_instruments_assembled": 0,
                        "deferred_candidates_preserved": 0,
                        "network_requests_performed": 0,
                        "private_access": False,
                        "screening": False,
                        "deep_evidence_collection": False,
                        "registry_mutation": False,
                        "reason": "held",
                    }
                )
                + "\n"
            )
            (artifact / "report.md").write_text("# blocked\n")
            run_json = root / "run.json"
            make_run(run_json)
            value = reviewer.review_artifact(
                artifact_root=artifact,
                source_run_json=run_json,
                source_run_id="40",
                source_run_attempt="1",
                contract_path=SOURCE_CONTRACT_PATH,
            )
            self.assertFalse(value["gate_passed"])
            self.assertEqual(value["candidate_count"], 0)

    def test_tampered_instrument_snapshot_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_success_artifact(root)
            path = root / "snapshot-artifact/universe-instruments.jsonl"
            path.write_bytes(path.read_bytes() + b"{}\n")
            run_json = root / "run.json"
            make_run(run_json)
            with self.assertRaises(reviewer.ReviewError):
                reviewer.review_artifact(
                    artifact_root=root / "snapshot-artifact",
                    source_run_json=run_json,
                    source_run_id="40",
                    source_run_attempt="1",
                    contract_path=SOURCE_CONTRACT_PATH,
                )

    def test_overlapping_candidate_sets_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_success_artifact(root)
            artifact = root / "snapshot-artifact"
            instruments = [
                json.loads(line)
                for line in (artifact / "universe-instruments.jsonl").read_text().splitlines()
            ]
            deferred = [
                json.loads(line)
                for line in (artifact / "universe-deferred.jsonl").read_text().splitlines()
            ]
            deferred[0]["candidate_id"] = instruments[0]["source_candidate_id"]
            deferred.sort(key=lambda item: item["candidate_id"])
            (artifact / "universe-deferred.jsonl").write_bytes(
                b"".join(reviewer.canon(item) for item in deferred)
            )
            run_json = root / "run.json"
            make_run(run_json)
            with self.assertRaises(reviewer.ReviewError):
                reviewer.review_artifact(
                    artifact_root=artifact,
                    source_run_json=run_json,
                    source_run_id="40",
                    source_run_attempt="1",
                    contract_path=SOURCE_CONTRACT_PATH,
                )

    def test_unexpected_raw_file_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_success_artifact(root)
            artifact = root / "snapshot-artifact"
            (artifact / "raw.json").write_text("{}\n")
            run_json = root / "run.json"
            make_run(run_json)
            with self.assertRaises(reviewer.ReviewError):
                reviewer.review_artifact(
                    artifact_root=artifact,
                    source_run_json=run_json,
                    source_run_id="40",
                    source_run_attempt="1",
                    contract_path=SOURCE_CONTRACT_PATH,
                )

    def test_wrong_source_run_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_success_artifact(root)
            run_json = root / "run.json"
            make_run(run_json)
            value = json.loads(run_json.read_text())
            value["name"] = "wrong"
            run_json.write_text(json.dumps(value) + "\n")
            with self.assertRaises(reviewer.ReviewError):
                reviewer.review_artifact(
                    artifact_root=root / "snapshot-artifact",
                    source_run_json=run_json,
                    source_run_id="40",
                    source_run_attempt="1",
                    contract_path=SOURCE_CONTRACT_PATH,
                )

    def test_review_output_is_exact_two_file_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_success_artifact(root)
            run_json = root / "run.json"
            make_run(run_json)
            value = reviewer.review_artifact(
                artifact_root=root / "snapshot-artifact",
                source_run_json=run_json,
                source_run_id="40",
                source_run_attempt="1",
                contract_path=SOURCE_CONTRACT_PATH,
            )
            output = root / "review-output"
            reviewer.write_review(output, value)
            self.assertEqual(reviewer.files_under(output), {"review.json", "review.md"})
            review = json.loads((output / "review.json").read_text())
            self.assertTrue(review["gate_passed"])
            self.assertEqual(
                review["review_core_sha256"],
                reviewer.digest(
                    reviewer.canon(
                        {key: value for key, value in review.items() if key != "review_core_sha256"}
                    )
                ),
            )

    def test_workflow_is_read_only_and_source_bound(self) -> None:
        text = WORKFLOW_PATH.read_text()
        self.assertIn(reviewer.SOURCE_WORKFLOW_NAME, text)
        self.assertIn("permissions:\n  contents: read", text)
        self.assertIn("actions: read", text)
        self.assertIn("persist-credentials: false", text)
        self.assertIn("review_immutable_universe_snapshot.py", text)
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
