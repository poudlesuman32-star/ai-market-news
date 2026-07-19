from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/verify-primary-source-coverage.yml"


class R10SourcePeriodDispatchTests(unittest.TestCase):
    def test_successful_verification_dispatches_exact_identity_without_write_authority(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("Dispatch exact successful run to private source-period validator", text)
        self.assertIn("ppi-r10-source-period-validation.yml/dispatches", text)
        self.assertIn("inputs[public_workflow_run_id]=${GITHUB_RUN_ID}", text)
        self.assertIn("inputs[public_workflow_run_attempt]=${GITHUB_RUN_ATTEMPT}", text)
        self.assertIn("inputs[public_head_sha]=${GITHUB_SHA}", text)
        self.assertIn("GH_TOKEN: ${{ secrets.PPI_CROSS_REPOSITORY_AUTOMATION }}", text)
        self.assertIn("permissions:\n  contents: read", text)
        self.assertNotIn("contents: write", text)
        self.assertNotIn("pull-requests: write", text)
        self.assertNotIn("repository_dispatch", text)
        self.assertNotIn("gh pr create", text)
        self.assertNotIn("gh pr merge", text)

    def test_weekday_schedule_uses_approved_four_slot_cadence_and_bounded_defaults(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn('schedule:\n    - cron: "15 1,7,13,19 * * 1-5"', text)
        self.assertEqual(text.count('cron: "15 1,7,13,19 * * 1-5"'), 1)
        self.assertIn("github.event_name == 'schedule' && vars.PPI_SEC_USER_AGENT", text)
        self.assertIn("github.event_name == 'schedule' && '30'", text)
        self.assertIn('if os.environ["GITHUB_EVENT_NAME"] == "schedule":', text)
        self.assertIn("assert value == 30", text)
        self.assertIn("cancel-in-progress: false", text)

    def test_artifact_is_retained_before_private_dispatch(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        upload = text.index("Retain immutable verification evidence")
        dispatch = text.index("Dispatch exact successful run to private source-period validator")
        boundary = text.index("Confirm read-only boundary")
        self.assertLess(upload, dispatch)
        self.assertLess(dispatch, boundary)
        self.assertIn("ppi-primary-source-coverage-${{ github.run_id }}-${{ github.run_attempt }}", text)


if __name__ == "__main__":
    unittest.main()
