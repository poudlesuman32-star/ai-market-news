from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEDULER = ROOT / ".github/workflows/ppi-public-migration-scheduler.yml"
RECOVERY_WORKFLOW = ROOT / ".github/workflows/ppi-private-recovery-after-billing-review.yml"
HOLD = ROOT / "scripts/disable_ppi_private_actions_after_startup_failure.py"
RERUN = ROOT / "scripts/rerun_ppi_private_after_billing_review.py"
STARTUP_DIAGNOSTIC = ROOT / "scripts/diagnose_ppi_private_startup_failure.py"
REMOVED_AUTO_DISPATCH = ROOT / "scripts/dispatch_ppi_private_post_enable_recovery.py"


class PpiPrivateBillingRecoveryTests(unittest.TestCase):
    def test_hourly_scheduler_allows_private_ci_and_never_auto_recovers(self) -> None:
        text = SCHEDULER.read_text(encoding="utf-8")
        self.assertIn("Allow private CI while keeping private dispatch held", text)
        self.assertIn("scripts/disable_ppi_private_actions_after_startup_failure.py", text)
        self.assertNotIn("Dispatch exact post-enable private recovery once", text)
        self.assertNotIn("scripts/enable_ppi_private_actions_once.py", text)
        self.assertNotIn("scripts/dispatch_ppi_private_post_enable_recovery.py", text)

    def test_ci_availability_control_is_bound_to_exact_historical_failure(self) -> None:
        text = HOLD.read_text(encoding="utf-8")
        self.assertIn('PRIVATE_REPOSITORY = "musksuman3/ai-signal-engine"', text)
        self.assertIn("PRIVATE_REPOSITORY_ID = 1290626648", text)
        self.assertIn("RECOVERY_RUN_ID = 30188784601", text)
        self.assertIn('EXPECTED_PRIVATE_HEAD_SHA = "49cbb0ce6aaa9bdb2e63dc54ac443a2b5cf6b312"', text)
        self.assertIn('payload={"enabled": True}', text)
        self.assertIn("private_actions_enabled_for_ci_private_dispatch_held", text)
        self.assertIn('"automatic_private_dispatch": False', text)
        self.assertNotIn("rerun-failed-jobs", text)
        self.assertNotIn("dispatches", text)
        self.assertNotIn("PPI_ALPHA_VANTAGE_API_KEY", text)
        self.assertNotIn("PPI_MARKETDATA_TOKEN", text)

    def test_manual_recovery_workflow_is_dispatch_only_and_exact(self) -> None:
        text = RECOVERY_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("\n  workflow_dispatch:\n", text)
        self.assertNotIn("\n  schedule:\n", text)
        self.assertNotIn("\n  push:\n", text)
        self.assertNotIn("\n  pull_request:\n", text)
        self.assertIn("RECOVER-PPI-PRIVATE-AFTER-BILLING-REVIEW", text)
        self.assertIn("permissions:\n  contents: read", text)
        self.assertIn("timeout-minutes: 10", text)
        self.assertIn("scripts/rerun_ppi_private_after_billing_review.py", text)
        self.assertIn("actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683", text)
        self.assertIn("persist-credentials: false", text)
        self.assertNotIn("contents:" + " write", text)
        self.assertNotIn("actions:" + " write", text)

    def test_rerun_requires_billing_review_and_zero_step_failure(self) -> None:
        text = RERUN.read_text(encoding="utf-8")
        self.assertIn('CONFIRMATION = "RECOVER-PPI-PRIVATE-AFTER-BILLING-REVIEW"', text)
        self.assertIn("RECOVERY_RUN_ID = 30188784601", text)
        self.assertIn('EXPECTED_PRIVATE_HEAD_SHA = "49cbb0ce6aaa9bdb2e63dc54ac443a2b5cf6b312"', text)
        self.assertIn("automatic rerun is forbidden", text)
        self.assertIn("/rerun-failed-jobs", text)
        self.assertIn('"github_owned_allowed": True', text)
        self.assertIn('"verified_allowed": False', text)
        self.assertIn('"patterns_allowed": []', text)
        self.assertNotIn("settings/billing/budgets", text)
        self.assertNotIn("budget_amount", text)
        self.assertNotIn("PPI_ALPHA_VANTAGE_API_KEY", text)
        self.assertNotIn("PPI_MARKETDATA_TOKEN", text)
        self.assertNotIn("raw_provider_payload", text)

    def test_startup_diagnostic_is_read_only_and_exact(self) -> None:
        text = STARTUP_DIAGNOSTIC.read_text(encoding="utf-8")
        self.assertIn("FAILED_RUN_ID = 30188784601", text)
        self.assertIn("pre_step_failure_without_runner_assignment", text)
        self.assertIn("/actions/jobs/{job_id}", text)
        self.assertIn("settings/billing/usage", text)
        self.assertNotIn("rerun-failed-jobs", text)
        self.assertNotIn("dispatches", text)

    def test_automatic_post_enable_dispatch_was_removed(self) -> None:
        self.assertFalse(REMOVED_AUTO_DISPATCH.exists())


if __name__ == "__main__":
    unittest.main()
