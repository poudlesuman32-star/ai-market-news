from __future__ import annotations

import ast
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/ppi_public_migration_schedule.json"
WORKFLOW = ROOT / ".github/workflows/ppi-public-migration-scheduler.yml"
AUTOPILOT = ROOT / "scripts/ppi_migration_autopilot.py"
AUTOPILOT_V2 = ROOT / "scripts/ppi_migration_autopilot_v2.py"
AUTOPILOT_V3 = ROOT / "scripts/ppi_migration_autopilot_v3.py"
AUTOPILOT_V4 = ROOT / "scripts/ppi_migration_autopilot_v4.py"
BOOTSTRAP_R2 = ROOT / "scripts/bootstrap_ppi_data_acquisition_r2.py"
PRIVATE_DIAGNOSTIC = ROOT / "scripts/enrich_ppi_private_queue_diagnostics.py"
PREPARE = ROOT / "scripts/prepare_ppi_target_update_branch.py"
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

    def test_workflow_runs_v4_controller_diagnostics_and_sha_pinned_actions(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("cron: '23 * * * *'", text)
        self.assertIn("permissions:\n  contents: read", text)
        self.assertIn("secrets.RAW_TOKEN", text)
        self.assertIn("secrets.PPI_ALPHA_VANTAGE_API_KEY", text)
        self.assertIn("secrets.PPI_MARKETDATA_TOKEN", text)
        self.assertIn("scripts/bootstrap_ppi_data_acquisition_r2.py", text)
        self.assertIn("scripts/ppi_migration_autopilot_v3.py", text)
        self.assertIn("scripts/ppi_migration_autopilot_v4.py", text)
        self.assertIn("python scripts/ppi_migration_autopilot_v4.py", text)
        self.assertIn("scripts/enrich_ppi_private_queue_diagnostics.py", text)
        self.assertIn("Enrich private queue and Actions usage diagnostics", text)
        self.assertIn("scripts/prepare_ppi_target_update_branch.py", text)
        self.assertIn("Prepare exact post-squash target update branch", text)
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

    def test_base_autopilot_keeps_dangerous_authority_disabled(self) -> None:
        text = AUTOPILOT.read_text(encoding="utf-8")
        self.assertIn('TARGET_REPOSITORY = "spoudel2010-ux/ppi-data-acquisition"', text)
        self.assertIn("TARGET_REPOSITORY_ID = 1312286476", text)
        self.assertIn('PRIVATE_REPOSITORY = "musksuman3/ai-signal-engine"', text)
        self.assertIn("PRIVATE_REPOSITORY_ID = 1290626648", text)
        self.assertIn('sync_secret(TARGET_REPOSITORY, "PPI_PRIVATE_HANDOFF_TOKEN"', text)
        self.assertIn('"registry_mutation": False', text)
        self.assertIn('"production": False', text)
        self.assertIn('"trading": False', text)
        self.assertIn('"r12": False', text)
        self.assertNotIn("--admin", text)

    def test_v2_discovers_current_target_pr_and_limits_retry_per_revision(self) -> None:
        text = AUTOPILOT_V2.read_text(encoding="utf-8")
        self.assertIn('"gh", "secret", "list"', text)
        self.assertIn('"--json", "name"', text)
        self.assertNotIn('"gh", "secret", "get"', text)
        self.assertIn("current_target_pr", text)
        self.assertIn("multiple open acquisition update pull requests exist", text)
        self.assertIn("same_revision", text)
        self.assertIn("current acquisition revision already failed in the past 24 hours", text)
        self.assertIn("src/fetch_yfinance_expectations.py", text)
        self.assertIn('"registry_mutation": False', text)
        self.assertIn('"production": False', text)
        self.assertIn('"trading": False', text)
        self.assertIn('"r12": False', text)

    def test_v3_uses_exact_r2_gate_current_sha_success_and_private_run_visibility(self) -> None:
        text = AUTOPILOT_V3.read_text(encoding="utf-8")
        self.assertIn("bootstrap_ppi_data_acquisition_r2.py", text)
        self.assertIn("target_gate_r2", text)
        self.assertIn("PPI-R11-PUBLIC-ACQUISITION-003-R2", text)
        self.assertIn("PPI-PUBLIC-COLLECTOR-003-R2", text)
        self.assertIn("latest_successful_current_public_run", text)
        self.assertIn('run.get("head_sha"', text)
        self.assertIn("main_sha", text)
        self.assertIn("private_run_for_public", text)
        self.assertIn("dispatch_private_with_visibility", text)
        self.assertIn("ORIGINAL_PRIVATE_DISPATCH", text)
        self.assertIn("time.sleep(5)", text)
        self.assertIn("private workflow run is not visible after 30 seconds", text)
        self.assertIn("v2.target_gate = target_gate_r2", text)
        self.assertIn("v2.base.latest_successful_public_run = latest_successful_current_public_run", text)
        self.assertIn("v2.base.dispatch_private_if_ready = dispatch_private_with_visibility", text)

    def test_v4_enforces_one_private_workflow_and_exact_minute_meter(self) -> None:
        text = AUTOPILOT_V4.read_text(encoding="utf-8")
        self.assertIn("is_authorized_private_workflow_run", text)
        self.assertIn('run.get("event")', text)
        self.assertIn('run.get("head_branch")', text)
        self.assertIn("within_authorization_window", text)
        self.assertIn("ACTIVE_STATUSES", text)
        self.assertIn("QUEUED_STATUSES", text)
        self.assertIn("PRIVATE_MINUTE_CEILING = 2000.0", text)
        self.assertIn("/actions/runs/{run_id}/cancel", text)
        self.assertIn("private final-analysis singleton retained", text)
        self.assertIn("cancelled redundant queued runs", text)
        self.assertIn("redundant queued runs could not be cancelled", text)
        self.assertIn("current public authorization window", text)
        self.assertIn("/settings/billing/actions", text)
        self.assertIn("gross usage alone is never used as a private-capacity gate", text)
        self.assertNotIn("settings/billing/usage/summary", text)
        self.assertIn("zero-job private run", text)
        self.assertIn("retry waits for the next month", text)
        self.assertIn("automatic retry is disabled", text)
        self.assertIn("v3.dispatch_private_with_visibility = dispatch_exact_private_run", text)
        self.assertNotIn("private_run_matches_public", text)
        self.assertNotIn("public_run_id_from_private_run", text)
        self.assertNotIn("PPI_ALPHA_VANTAGE_API_KEY", text)
        self.assertNotIn("PPI_MARKETDATA_TOKEN", text)
        self.assertNotIn("raw_provider_payload", text)

    def test_r2_bootstrap_has_exact_fifteen_file_allowlist_and_noop_path(self) -> None:
        source = BOOTSTRAP_R2.read_text(encoding="utf-8")
        tree = ast.parse(source)
        assignment = next(
            node
            for node in tree.body
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "REQUIRED_R2_PATHS" for target in node.targets)
        )
        paths = ast.literal_eval(assignment.value)
        self.assertEqual(len(paths), 15)
        self.assertIn("contracts/PPI-R11-PUBLIC-ACQUISITION-003-R1.json", paths)
        self.assertIn("contracts/PPI-R11-PUBLIC-ACQUISITION-003-R2.json", paths)
        self.assertIn("contracts/PPI-PUBLIC-COLLECTOR-003-R1.json", paths)
        self.assertIn("contracts/PPI-PUBLIC-COLLECTOR-003-R2.json", paths)
        self.assertIn("src/collect_raw_provider_evidence_r2.py", paths)
        self.assertIn("src/fetch_yfinance_expectations.py", paths)
        self.assertIn("git_blob_sha", source)
        self.assertIn("branch_matches_desired", source)
        self.assertIn("base_matches_desired", source)
        self.assertIn("target_already_current", source)
        self.assertIn("if final_branch_sha == final_base_sha", source)
        self.assertIn("continue", source)

    def test_private_queue_diagnostic_is_public_only_and_does_not_misread_gross_usage(self) -> None:
        text = PRIVATE_DIAGNOSTIC.read_text(encoding="utf-8")
        self.assertIn('PRIVATE_REPOSITORY = "musksuman3/ai-signal-engine"', text)
        self.assertIn("PRIVATE_REPOSITORY_ID = 1290626648", text)
        self.assertIn("EXPECTED_INCLUDED_PRIVATE_MINUTES = 2000", text)
        self.assertIn("configured_private_minute_ceiling", text)
        self.assertIn("/actions/runs/{run_id}/jobs?filter=latest", text)
        self.assertIn("settings/billing/actions", text)
        self.assertIn("settings/billing/usage/summary", text)
        self.assertIn('version="2026-03-10"', text)
        self.assertIn("remains queued with no allocated job", text)
        self.assertIn("exact included-minute ceiling reached", text)
        self.assertIn("included-minute ceiling is reached", text)
        self.assertIn("gross Actions usage is fully discounted", text)
        self.assertIn("does not prove private included-minute exhaustion", text)
        self.assertIn('"registry_mutation"', text)
        self.assertNotIn("dispatches", text)
        self.assertNotIn("raw_provider_payload", text)
        self.assertNotIn("PPI_ALPHA_VANTAGE_API_KEY", text)
        self.assertNotIn("PPI_MARKETDATA_TOKEN", text)

    def test_stale_target_branch_cleaner_is_exact_and_fail_closed(self) -> None:
        text = PREPARE.read_text(encoding="utf-8")
        self.assertIn("TARGET_REPOSITORY_ID = 1312286476", text)
        self.assertIn("multiple open target update pull requests exist", text)
        self.assertIn('"src/collect_raw_provider_evidence_r2.py"', text)
        self.assertIn('"src/fetch_yfinance_expectations.py"', text)
        self.assertIn('"contracts/PPI-R11-PUBLIC-ACQUISITION-003-R2.json"', text)
        self.assertIn('"contracts/PPI-PUBLIC-COLLECTOR-003-R2.json"', text)
        self.assertIn('payload={"sha": main_sha, "force": True}', text)
        self.assertIn("open_target_update_has_content_changes", text)

    def test_status_issue_is_sanitized_preserves_zero_and_displays_queue_diagnostics(self) -> None:
        text = STATUS_PUBLISHER.read_text(encoding="utf-8")
        self.assertIn('SOURCE_REPOSITORY = "poudlesuman32-star/ai-market-news"', text)
        self.assertIn("SOURCE_REPOSITORY_ID = 1290414659", text)
        self.assertIn("STATUS_ISSUE = 83", text)
        self.assertIn('"ghp_"', text)
        self.assertIn('"github_pat_"', text)
        self.assertIn('"Bearer "', text)
        self.assertIn("dangerous authority unexpectedly enabled", text)
        self.assertIn('"" if value is None else str(value)', text)
        self.assertIn("## Private queue diagnostics", text)
        self.assertIn("Allocated jobs", text)
        self.assertIn("Actions minutes included", text)
        self.assertIn("Capacity interpretation", text)
        self.assertNotIn("raw_provider_payload", text)
        self.assertNotIn("private score", text.lower())


if __name__ == "__main__":
    unittest.main()
