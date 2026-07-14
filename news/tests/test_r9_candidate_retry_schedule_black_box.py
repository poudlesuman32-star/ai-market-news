from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/collect-public-news-live.yml"
EXPECTED_CRON = "15 1,7,13,19 * * 1-5"
EXPECTED_CONTRACT_ID = "PPI-R9-CANDIDATE-RETRY-SCHEDULE-002"
EXPECTED_CONTRACT_SHA256 = "3d5dc56da9e845a451a4523272175c8b1eb6959cd25fb8b97502435aa978bd8e"


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


class R9CandidateRetryScheduleBlackBoxTests(unittest.TestCase):
    def setUp(self) -> None:
        self.workflow = WORKFLOW.read_text(encoding="utf-8")

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


if __name__ == "__main__":
    unittest.main()
