from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/collect-public-news-live.yml"
AUTOMATED_PUBLICATION_WORKFLOW = ROOT / ".github/workflows/ppi-r9-automated-publication.yml"
EXPECTED_CRON = "15 1,7,13,19 * * 1-5"
EXPECTED_CONTRACT_ID = "PPI-R9-CANDIDATE-RETRY-SCHEDULE-002"
EXPECTED_CONTRACT_SHA256 = "3d5dc56da9e845a451a4523272175c8b1eb6959cd25fb8b97502435aa978bd8e"
AUTONOMY_CONTRACT_ID = "PPI-R9-AUTONOMY-002"
AUTONOMY_CONTRACT_SHA256 = "2f29d15d2f4447c2f17327277614c274e051c2259b34af054ee6daa1553ff704"


class ScheduleShapeError(ValueError):
    pass


def validate_schedule_text(text: str) -> None:
    expressions = re.findall(r"^\s*-\s*cron:\s*[\"']([^\"']+)[\"']\s*$", text, re.MULTILINE)
    if expressions != [EXPECTED_CRON]:
        raise ScheduleShapeError(f"unexpected cron expressions: {expressions}")

    minute, hour_field, day_of_month, month, day_of_week = expressions[0].split()
    if minute != "15" or day_of_month != "*" or month != "*" or day_of_week != "1-5":
        raise ScheduleShapeError("schedule is not the approved weekday UTC shape")

    hours = [int(value) for value in hour_field.split(",")]
    if hours != [1, 7, 13, 19]:
        raise ScheduleShapeError("approved UTC slots changed")
    intervals = [hours[index + 1] - hours[index] for index in range(len(hours) - 1)]
    intervals.append(24 + hours[0] - hours[-1])
    if intervals != [6, 6, 6, 6]:
        raise ScheduleShapeError("schedule is not six-hourly")

    required = {
        "workflow_dispatch:",
        "PPI_SEC_USER_AGENT",
        'SCHEDULED_LOOKBACK_DAYS: "30"',
        "contents: read",
        "persist-credentials: false",
        "cancel-in-progress: false",
        EXPECTED_CONTRACT_ID,
        EXPECTED_CONTRACT_SHA256,
        "retry_schedule_contract.json",
    }
    missing = sorted(value for value in required if value not in text)
    if missing:
        raise ScheduleShapeError(f"required boundary missing: {missing}")

    lowered = text.lower()
    forbidden = (
        "contents: write",
        "git push",
        "repository_dispatch",
        "public-news-data",
        "write_mmm",
        "write_raw_data",
        "place_order",
        "automatic_trading",
    )
    present = [value for value in forbidden if value in lowered]
    if present:
        raise ScheduleShapeError(f"candidate workflow gained prohibited authority: {present}")


def validate_automated_publication_boundary(text: str) -> None:
    required = {
        "name: PPI R9 automated publication and private dispatch",
        "workflow_run:",
        "- PPI public news live primary-source preview",
        "- PPI automated read-only live primary-source candidate",
        "github.event.workflow_run.conclusion == 'success'",
        "github.event.workflow_run.head_branch == 'main'",
        "github.event.workflow_run.event != 'pull_request'",
        AUTONOMY_CONTRACT_ID,
        AUTONOMY_CONTRACT_SHA256,
        "ppi-public-news-live-preview-${SOURCE_RUN_ID}-${SOURCE_RUN_ATTEMPT}",
        "ppi-readonly-live-candidate-${SOURCE_RUN_ID}-${SOURCE_RUN_ATTEMPT}",
        "Unsupported R9 source workflow",
        "Enforce exact autonomous candidate gate",
        "Publish immutable Commit A B C transaction",
        "ppi_public_snapshot_ready",
        "client_payload[source_workflow_name]",
        "publication_authorization.json",
        "'manual_approval_required': False",
        "'prohibited_actions_enabled': False",
    }
    missing = sorted(value for value in required if value not in text)
    if missing:
        raise ScheduleShapeError(f"autonomous boundary missing: {missing}")
    if text.index("Enforce exact autonomous candidate gate") > text.index("Publish immutable Commit A B C transaction"):
        raise ScheduleShapeError("publication precedes candidate validation")
    if "environment: ppi-r9-manual-approval" in text:
        raise ScheduleShapeError("automated path regained a manual environment gate")
    if "schedule:" in text:
        raise ScheduleShapeError("publication workflow gained an independent schedule")


class R9CandidateRetryScheduleBlackBoxTests(unittest.TestCase):
    def setUp(self) -> None:
        self.workflow = WORKFLOW.read_text(encoding="utf-8")
        self.automated_publication = AUTOMATED_PUBLICATION_WORKFLOW.read_text(encoding="utf-8")

    def test_documented_workflow_has_exact_four_weekday_slots(self) -> None:
        validate_schedule_text(self.workflow)

    def test_prior_once_daily_cron_fails_closed(self) -> None:
        changed = self.workflow.replace(EXPECTED_CRON, "15 13 * * 1-5")
        with self.assertRaisesRegex(ScheduleShapeError, "unexpected cron expressions"):
            validate_schedule_text(changed)

    def test_weekend_schedule_fails_closed(self) -> None:
        changed = self.workflow.replace(EXPECTED_CRON, "15 1,7,13,19 * * 0-6")
        with self.assertRaisesRegex(ScheduleShapeError, "unexpected cron expressions"):
            validate_schedule_text(changed)

    def test_extra_schedule_fails_closed(self) -> None:
        changed = self.workflow.replace(
            f'- cron: "{EXPECTED_CRON}"',
            f'- cron: "{EXPECTED_CRON}"\n    - cron: "45 4 * * 1-5"',
        )
        with self.assertRaisesRegex(ScheduleShapeError, "unexpected cron expressions"):
            validate_schedule_text(changed)

    def test_higher_frequency_schedule_fails_closed(self) -> None:
        changed = self.workflow.replace(EXPECTED_CRON, "15 */3 * * 1-5")
        with self.assertRaisesRegex(ScheduleShapeError, "unexpected cron expressions"):
            validate_schedule_text(changed)

    def test_write_permission_fails_closed(self) -> None:
        changed = self.workflow.replace("contents: read", "contents: write", 1)
        with self.assertRaisesRegex(ScheduleShapeError, "required boundary missing|prohibited authority"):
            validate_schedule_text(changed)

    def test_contract_hash_change_fails_closed(self) -> None:
        changed = self.workflow.replace(EXPECTED_CONTRACT_SHA256, "0" * 64)
        with self.assertRaisesRegex(ScheduleShapeError, "required boundary missing"):
            validate_schedule_text(changed)

    def test_manual_diagnostic_interface_is_preserved(self) -> None:
        self.assertIn("sec_user_agent:", self.workflow)
        self.assertIn("lookback_days:", self.workflow)
        self.assertIn('default: "30"', self.workflow)
        self.assertIn("assert 1 <= value <= 30", self.workflow)

    def test_qualifying_candidate_cascades_only_under_frozen_autonomy_contract(self) -> None:
        validate_automated_publication_boundary(self.automated_publication)

    def test_manual_gate_or_changed_autonomy_hash_fails_closed(self) -> None:
        changed = self.automated_publication.replace(AUTONOMY_CONTRACT_SHA256, "0" * 64)
        changed += "\nenvironment: ppi-r9-manual-approval\n"
        with self.assertRaisesRegex(ScheduleShapeError, "autonomous boundary missing|manual environment gate"):
            validate_automated_publication_boundary(changed)


if __name__ == "__main__":
    unittest.main()
