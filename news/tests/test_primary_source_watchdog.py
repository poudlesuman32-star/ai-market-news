from __future__ import annotations

import unittest
from datetime import datetime, timezone
from pathlib import Path

from ai_market_news.primary_source_watchdog import WORKFLOW_PATH, evaluate, expected_slot

ROOT = Path(__file__).resolve().parents[2]
WATCHDOG_WORKFLOW = ROOT / ".github/workflows/verify-primary-source-coverage-watchdog.yml"


def run(run_id: int, *, created_at: str, path: str = WORKFLOW_PATH, branch: str = "main", event: str = "schedule", status: str = "completed") -> dict[str, object]:
    return {
        "id": run_id,
        "created_at": created_at,
        "path": path,
        "head_branch": branch,
        "event": event,
        "status": status,
    }


class PrimarySourceWatchdogTests(unittest.TestCase):
    def test_expected_slot_uses_latest_weekday_slot(self) -> None:
        now = datetime(2026, 7, 20, 20, 0, tzinfo=timezone.utc)
        self.assertEqual(expected_slot(now).isoformat(), "2026-07-20T19:15:00+00:00")
        early_monday = datetime(2026, 7, 20, 0, 30, tzinfo=timezone.utc)
        self.assertEqual(expected_slot(early_monday).isoformat(), "2026-07-17T19:15:00+00:00")

    def test_existing_slot_run_prevents_dispatch(self) -> None:
        result = evaluate(
            {"workflow_runs": [run(100, created_at="2026-07-20T19:16:00Z", status="in_progress")]},
            now_utc="2026-07-20T20:00:00Z",
        )
        self.assertEqual(result["status"], "covered")
        self.assertFalse(result["dispatch_required"])
        self.assertEqual(result["matching_run_ids"], [100])

    def test_missing_or_wrong_identity_requires_exact_dispatch(self) -> None:
        history = {
            "workflow_runs": [
                run(1, created_at="2026-07-20T19:16:00Z", path=".github/workflows/other.yml"),
                run(2, created_at="2026-07-20T19:16:00Z", branch="feature"),
                run(3, created_at="2026-07-20T19:16:00Z", event="pull_request"),
                run(4, created_at="2026-07-20T19:16:00Z", status="cancelled"),
            ]
        }
        result = evaluate(history, now_utc="2026-07-20T20:00:00Z")
        self.assertEqual(result["status"], "dispatch_required")
        self.assertTrue(result["dispatch_required"])
        self.assertEqual(result["workflow_path"], WORKFLOW_PATH)
        self.assertEqual(result["dispatch_ref"], "main")

    def test_watchdog_has_only_bounded_action_authority(self) -> None:
        text = WATCHDOG_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn('cron: "0 2,8,14,20 * * 1-5"', text)
        self.assertIn("actions: write", text)
        self.assertIn("contents: read", text)
        self.assertIn("verify-primary-source-coverage.yml", text)
        self.assertIn("--ref main", text)
        for forbidden in (
            "contents: write", "pull-requests: write", "id-token: write",
            "git push", "repository_dispatch", "gh pr", "registration_authorized",
        ):
            self.assertNotIn(forbidden, text)


if __name__ == "__main__":
    unittest.main()
