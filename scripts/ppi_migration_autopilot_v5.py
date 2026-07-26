#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import ppi_migration_autopilot_v4 as v4

HOLD_REASON = (
    "Automatic private final-analysis dispatch is disabled after pre-runner failure 30188784601; "
    "only the manual billing-reviewed recovery workflow is authorized."
)


def held_private_dispatch(token: str, public_run: dict[str, Any]) -> tuple[bool, str]:
    del token, public_run
    return False, HOLD_REASON


def output_root_from_argv() -> Path:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--output-root", required=True)
    args, _ = parser.parse_known_args()
    return Path(args.output_root)


def unique_append(items: list[str], value: str) -> None:
    if value not in items:
        items.append(value)


def enforce_report_hold(output_root: Path) -> None:
    report_path = output_root / "autopilot.json"
    if not report_path.is_file():
        raise RuntimeError("autopilot report is missing after v4 reconciliation")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if not isinstance(report, dict):
        raise RuntimeError("autopilot report must be an object")

    authority = report.get("authority")
    if not isinstance(authority, dict):
        raise RuntimeError("autopilot authority is missing")
    authority["private_final_analysis_dispatch"] = False
    authority["manual_private_recovery_after_billing_review"] = True
    authority["billing_budget_mutation"] = False

    blocked = report.get("blocked_reasons")
    if not isinstance(blocked, list):
        blocked = []
        report["blocked_reasons"] = blocked
    unique_append(blocked, HOLD_REASON)

    actions = report.get("actions")
    if not isinstance(actions, list):
        actions = []
        report["actions"] = actions
    unique_append(actions, "Kept automatic private dispatch and cancellation disabled under the billing-review hold.")

    report["status"] = "blocked"
    report["private_execution_state"] = "held_after_pre_runner_failure"
    report["manual_recovery_workflow"] = "ppi-private-recovery-after-billing-review.yml"
    report["manual_recovery_confirmation"] = "RECOVER-PPI-PRIVATE-AFTER-BILLING-REVIEW"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    markdown_path = output_root / "autopilot.md"
    if markdown_path.exists():
        with markdown_path.open("a", encoding="utf-8") as handle:
            handle.write("\n## Private execution hold\n\n")
            handle.write(f"- {HOLD_REASON}\n")


def main() -> int:
    output_root = output_root_from_argv()
    v4.dispatch_exact_private_run = held_private_dispatch
    result = v4.main()
    enforce_report_hold(output_root)
    return result


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"v5 autopilot failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
