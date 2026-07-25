from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/ppi_public_migration_schedule.json"
WORKFLOW = ROOT / ".github/workflows/ppi-public-migration-scheduler.yml"
SCRIPT = ROOT / "scripts/build_ppi_public_migration_readiness.py"


class PpiPublicMigrationSchedulerTests(unittest.TestCase):
    def test_only_gate_zero_task_one_is_active(self) -> None:
        value = json.loads(CONFIG.read_text(encoding="utf-8"))
        self.assertTrue(value["enabled"])
        self.assertEqual(value["phase"], "gate-0-public-readiness")
        self.assertEqual(value["active_task_id"], "T01")
        self.assertEqual(value["active_task"]["id"], "T01")
        self.assertEqual(
            [item["id"] for item in value["task_queue"] if item["status"] == "active"],
            ["T01"],
        )
        self.assertEqual(value["schedule"]["cron_utc"], "15 14 * * 1-5")

    def test_scheduler_grants_no_downstream_authority(self) -> None:
        value = json.loads(CONFIG.read_text(encoding="utf-8"))
        authority = value["authority"]
        self.assertEqual(authority["authorized_actions"], [])
        for key, allowed in authority.items():
            if key == "authorized_actions":
                continue
            self.assertFalse(allowed, key)

    def test_workflow_is_public_read_only_and_sha_pinned(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        runtime = text.split("      - name: Validate scheduler boundary", 1)[0]
        self.assertIn("\n  workflow_dispatch:\n", text)
        self.assertIn("cron: '15 14 * * 1-5'", text)
        self.assertIn("permissions:\n  contents: read", text)
        self.assertIn("actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683", text)
        self.assertIn("actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02", text)
        self.assertIn("persist-credentials: false", text)
        for forbidden in (
            "repository_" + "dispatch",
            "workflow_" + "run",
            "contents:" + " write",
            "pull-requests:" + " write",
            "actions:" + " write",
            "issues:" + " write",
            "git " + "push",
            "gh pr " + "merge",
            "secrets." + "RAW_TOKEN",
            "musksuman3/" + "ai-signal-engine",
        ):
            self.assertNotIn(forbidden, runtime)

    def test_script_is_read_only(self) -> None:
        text = SCRIPT.read_text(encoding="utf-8")
        for forbidden in (
            'method="POST"',
            'method="PUT"',
            'method="PATCH"',
            'method="DELETE"',
            "Authorization",
            "PPI_ALPHA_VANTAGE_API_KEY",
            "PPI_MARKETDATA_TOKEN",
            'os.environ.get("RAW_TOKEN")',
        ):
            self.assertNotIn(forbidden, text)


if __name__ == "__main__":
    unittest.main()
