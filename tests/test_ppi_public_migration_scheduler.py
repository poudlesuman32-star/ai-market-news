from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/ppi_public_migration_schedule.json"
WORKFLOW = ROOT / ".github/workflows/ppi-public-migration-scheduler.yml"
AUTOPILOT = ROOT / "scripts/ppi_migration_autopilot.py"
AUTOPILOT_V2 = ROOT / "scripts/ppi_migration_autopilot_v2.py"
STATUS_PUBLISHER = ROOT / "scripts/publish_ppi_autopilot_status.py"


class PpiMigrationAutopilotTests(unittest.TestCase):
    def test_autopilot_is_hourly_and_requires_no_human_dispatch(self) -> None:
        value = json.loads(CONFIG.read_text(encoding="utf-8"))
        self.assertTrue(value["enabled"])
        self.assertEqual(value["schema_version"], "2.0.0")
        self.assertEqual(value["mode"], "idempotent_reconciliation")
        self.assertEqual(value["cron_utc"], "23 * * * *")
        self.assertTrue(value["automatic_task_advancement"])
        self.assertFalse(value["human_dispatch_required"])
        self.assertTrue(value["fail_closed"])

    def test_authorized_actions_are_narrow_and_dangerous_authority_is_disabled(self) -> None:
        authority = json.loads(CONFIG.read_text(encoding="utf-8"))["authority"]
        for key in (
            "bootstrap_sync",
            "target_secret_sync",
            "target_pr_merge_after_machine_gates",
            "public_collection_dispatch",
            "private_final_analysis_dispatch",
        ):
            self.assertTrue(authority[key], key)
        for key in (
            "registry_mutation",
            "production",
            "publication",
            "broker",
            "orders",
            "trading",
            "mmm_raw_data",
            "r12",
        ):
            self.assertFalse(authority[key], key)

    def test_workflow_uses_approved_secret_bindings_and_sha_pinned_actions(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("cron: '23 * * * *'", text)
        self.assertIn("permissions:\n  contents: read", text)
        self.assertIn("secrets.RAW_TOKEN", text)
        self.assertIn("secrets.PPI_ALPHA_VANTAGE_API_KEY", text)
        self.assertIn("secrets.PPI_MARKETDATA_TOKEN", text)
        self.assertIn("scripts/ppi_migration_autopilot_v2.py", text)
        self.assertIn("scripts/publish_ppi_autopilot_status.py", text)
        self.assertIn("actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683", text)
        self.assertIn("actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02", text)
        self.assertIn("persist-credentials: false", text)
        for forbidden in (
            "contents:" + " write",
            "pull-requests:" + " write",
            "issues:" + " write",
            "actions:" + " write",
            "production_authorized: true",
            "trading_authorized: true",
            "r12_authorized: true",
        ):
            self.assertNotIn(forbidden, text)

    def test_autopilot_is_exact_repo_fail_closed_and_deduplicated(self) -> None:
        text = AUTOPILOT.read_text(encoding="utf-8")
        self.assertIn('TARGET_REPOSITORY = "spoudel2010-ux/ppi-data-acquisition"', text)
        self.assertIn("TARGET_REPOSITORY_ID = 1312286476", text)
        self.assertIn('PRIVATE_REPOSITORY = "musksuman3/ai-signal-engine"', text)
        self.assertIn("PRIVATE_REPOSITORY_ID = 1290626648", text)
        self.assertIn('sync_secret(TARGET_REPOSITORY, "PPI_PRIVATE_HANDOFF_TOKEN"', text)
        self.assertIn("daily public collection retry ceiling reached", text)
        self.assertIn("target_pr_merge_after_machine_gates", text)
        self.assertIn('"registry_mutation": False', text)
        self.assertIn('"production": False', text)
        self.assertIn('"trading": False', text)
        self.assertIn('"r12": False', text)
        self.assertNotIn("--admin", text)

    def test_v2_probes_secret_names_without_reading_values(self) -> None:
        text = AUTOPILOT_V2.read_text(encoding="utf-8")
        self.assertIn('"gh", "secret", "list"', text)
        self.assertIn('"--json", "name"', text)
        self.assertNotIn('"gh", "secret", "get"', text)
        self.assertNotIn("gh secret get", text)
        self.assertIn("collector will fail fast", text)
        self.assertIn("latest public collection run", text.lower())
        self.assertIn('"registry_mutation": False', text)
        self.assertIn('"production": False', text)
        self.assertIn('"trading": False', text)
        self.assertIn('"r12": False', text)

    def test_status_issue_is_sanitized_and_dangerous_authority_fails_closed(self) -> None:
        text = STATUS_PUBLISHER.read_text(encoding="utf-8")
        self.assertIn('SOURCE_REPOSITORY = "poudlesuman32-star/ai-market-news"', text)
        self.assertIn("SOURCE_REPOSITORY_ID = 1290414659", text)
        self.assertIn("STATUS_ISSUE = 83", text)
        self.assertIn('"ghp_"', text)
        self.assertIn('"github_pat_"', text)
        self.assertIn('"Bearer "', text)
        self.assertIn("dangerous authority unexpectedly enabled", text)
        self.assertNotIn("raw_provider_payload", text)
        self.assertNotIn("private score", text.lower())


if __name__ == "__main__":
    unittest.main()
