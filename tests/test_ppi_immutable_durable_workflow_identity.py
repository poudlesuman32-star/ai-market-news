from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


assembler = load(
    "immutable_assembler_hardened",
    "assemble_immutable_universe_snapshot_hardened.py",
)
reviewer = load(
    "immutable_reviewer_hardened",
    "review_immutable_universe_snapshot_hardened.py",
)


class ImmutableDurableWorkflowIdentityTests(unittest.TestCase):
    @staticmethod
    def stable_review_run(**overrides: object) -> dict:
        value = {
            "id": 34081955551,
            "run_attempt": 1,
            "name": "Stable ID review from allocation 34081406609-1 on deadbeef",
            "path": assembler.REVIEW_WORKFLOW_PATH,
            "event": assembler.REVIEW_EVENT,
            "repository": {"full_name": assembler.base.EXPECTED_REPOSITORY},
            "head_branch": "main",
            "status": "completed",
            "conclusion": "success",
        }
        value.update(overrides)
        return value

    @staticmethod
    def snapshot_run(**overrides: object) -> dict:
        value = {
            "id": 41,
            "run_attempt": 1,
            "name": "Immutable snapshot from stable ID review 34081955551-1 on deadbeef",
            "path": reviewer.SOURCE_WORKFLOW_PATH,
            "event": reviewer.SOURCE_EVENT,
            "repository": {"full_name": reviewer.base.EXPECTED_REPOSITORY},
            "head_branch": "main",
            "status": "completed",
            "conclusion": "success",
        }
        value.update(overrides)
        return value

    def test_assembler_accepts_custom_run_name_with_durable_identity(self) -> None:
        checks = assembler.validate_run(
            self.stable_review_run(), "34081955551", "1"
        )
        self.assertTrue(checks["workflow_path"])
        self.assertTrue(checks["event"])
        self.assertNotIn("name", checks)

    def test_assembler_rejects_wrong_review_path_or_event(self) -> None:
        with self.assertRaises(assembler.base.SnapshotError):
            assembler.validate_run(
                self.stable_review_run(path=".github/workflows/wrong.yml"),
                "34081955551",
                "1",
            )
        with self.assertRaises(assembler.base.SnapshotError):
            assembler.validate_run(
                self.stable_review_run(event="push"), "34081955551", "1"
            )

    def test_reviewer_accepts_custom_snapshot_run_name_with_durable_identity(self) -> None:
        checks = reviewer.validate_source_run(self.snapshot_run(), "41", "1")
        self.assertTrue(checks["workflow_path"])
        self.assertTrue(checks["event"])
        self.assertNotIn("name", checks)

    def test_reviewer_rejects_wrong_snapshot_path_or_event(self) -> None:
        with self.assertRaises(reviewer.base.ReviewError):
            reviewer.validate_source_run(
                self.snapshot_run(path=".github/workflows/wrong.yml"), "41", "1"
            )
        with self.assertRaises(reviewer.base.ReviewError):
            reviewer.validate_source_run(self.snapshot_run(event="push"), "41", "1")


if __name__ == "__main__":
    unittest.main()
