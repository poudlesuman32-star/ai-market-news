from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "hardened_reviewer",
    ROOT / "scripts" / "review_stable_instrument_id_allocation_hardened.py",
)
hardened = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(hardened)


class StableIdDurableSourceIdentityTests(unittest.TestCase):
    @staticmethod
    def run_metadata(**overrides: object) -> dict:
        value = {
            "id": 34081406609,
            "run_attempt": 1,
            "name": "Stable ID allocation from OpenFIGI review 33262596949-1",
            "path": hardened.SOURCE_WORKFLOW_PATH,
            "event": hardened.SOURCE_EVENT,
            "repository": {"full_name": hardened.EXPECTED_REPOSITORY},
            "head_branch": "main",
            "status": "completed",
            "conclusion": "success",
        }
        value.update(overrides)
        return value

    def test_custom_run_name_is_accepted_when_durable_identity_matches(self) -> None:
        checks = hardened.validate_source_run(
            self.run_metadata(), "34081406609", "1"
        )
        self.assertTrue(checks["workflow_path"])
        self.assertTrue(checks["event"])
        self.assertNotIn("name", checks)

    def test_wrong_workflow_path_fails(self) -> None:
        with self.assertRaises(hardened.ReviewError):
            hardened.validate_source_run(
                self.run_metadata(path=".github/workflows/wrong.yml"),
                "34081406609",
                "1",
            )

    def test_wrong_event_fails(self) -> None:
        with self.assertRaises(hardened.ReviewError):
            hardened.validate_source_run(
                self.run_metadata(event="push"), "34081406609", "1"
            )

    def test_blocked_artifact_uses_durable_source_identity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            artifact = root / "artifact"
            artifact.mkdir()
            (artifact / "blocked.json").write_text(
                json.dumps(
                    {
                        "contract_id": hardened.base.SOURCE_CONTRACT_ID,
                        "status": "blocked",
                        "reason": "upstream held",
                        "stable_instrument_ids_allocated": 0,
                        "private_access": False,
                        "screening": False,
                        "deep_evidence_collection": False,
                        "registry_mutation": False,
                    },
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
            (artifact / "report.md").write_text("# Blocked\n", encoding="utf-8")
            run_json = root / "run.json"
            run_json.write_text(
                json.dumps(self.run_metadata(), indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            result = hardened.review_artifact(
                artifact_root=artifact,
                source_run_json=run_json,
                source_run_id="34081406609",
                source_run_attempt="1",
                contract_path=ROOT
                / "contracts"
                / "PPI-STABLE-INSTRUMENT-ID-ALLOCATION-PILOT-001-R1.json",
            )
            self.assertFalse(result["gate_passed"])
            self.assertTrue(result["source_run_checks"]["workflow_path"])
            self.assertTrue(result["source_run_checks"]["event"])


if __name__ == "__main__":
    unittest.main()
