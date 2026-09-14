#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any
from urllib.parse import quote

import ppi_migration_autopilot_v4 as v4

MIGRATED_TARGET_REPOSITORY = "MarketMakingLFG/ppi-data-acquisition"
MIGRATED_TARGET_REPOSITORY_ID = 1312286476
PROTECTED_ENVIRONMENT = "r11-public-acquisition-protected"
REQUIRED_DEPLOYMENT_BRANCH = "main"
ORIGINAL_PUBLIC_DISPATCH_GATE = v4.v3.v2.should_dispatch_public

HOLD_REASON = (
    "Automatic private final-analysis dispatch is disabled after pre-runner failure 30188784601; "
    "only the manual billing-reviewed recovery workflow is authorized."
)


def held_private_dispatch(token: str, public_run: dict[str, Any]) -> tuple[bool, str]:
    del token, public_run
    return False, HOLD_REASON


def _api(token: str, path: str, allowed: tuple[int, ...] = (200,)) -> tuple[int, Any]:
    return v4.v3.v2.base.api(
        "GET",
        path,
        token=token,
        allowed_statuses=allowed,
    )


def _custom_branch_allows_main(token: str) -> bool:
    encoded = quote(PROTECTED_ENVIRONMENT, safe="")
    status, value = _api(
        token,
        f"/repos/{MIGRATED_TARGET_REPOSITORY}/environments/{encoded}/deployment-branch-policies?per_page=100",
        allowed=(200, 404),
    )
    if status != 200 or not isinstance(value, dict):
        return False
    policies = value.get("branch_policies")
    if not isinstance(policies, list):
        return False
    return any(
        isinstance(item, dict)
        and str(item.get("name") or "") == REQUIRED_DEPLOYMENT_BRANCH
        for item in policies
    )


def protected_environment_ready(token: str) -> tuple[bool, str]:
    """Read only target environment policy and fail closed on unknown state."""
    encoded = quote(PROTECTED_ENVIRONMENT, safe="")
    status, environment = _api(
        token,
        f"/repos/{MIGRATED_TARGET_REPOSITORY}/environments/{encoded}",
        allowed=(200, 404),
    )
    if status == 404:
        return False, f"public collection held: protected environment {PROTECTED_ENVIRONMENT} is not configured"
    if not isinstance(environment, dict):
        return False, "public collection held: protected environment response is invalid"
    if environment.get("can_admins_bypass") is not False:
        return False, "public collection held: protected environment administrator bypass is not denied"

    branch_policy = environment.get("deployment_branch_policy")
    if not isinstance(branch_policy, dict):
        return False, "public collection held: protected environment deployment branch policy is missing"
    protected_branches = branch_policy.get("protected_branches") is True
    custom_branches = branch_policy.get("custom_branch_policies") is True
    if custom_branches and not _custom_branch_allows_main(token):
        return False, "public collection held: custom deployment branch policy does not prove main is allowed"
    if not protected_branches and not custom_branches:
        return False, "public collection held: protected environment has no deployment branch restriction"

    rules_status, rules_value = _api(
        token,
        f"/repos/{MIGRATED_TARGET_REPOSITORY}/environments/{encoded}/deployment_protection_rules",
        allowed=(200, 404),
    )
    if rules_status != 200 or not isinstance(rules_value, dict):
        return False, "public collection held: custom deployment protection rules are unavailable"
    rules = rules_value.get("custom_deployment_protection_rules")
    if not isinstance(rules, list) or not rules:
        return False, "public collection held: no custom deployment protection rule is enabled"
    identified_rules = [
        item
        for item in rules
        if isinstance(item, dict)
        and isinstance(item.get("id"), int)
        and item["id"] > 0
        and isinstance(item.get("app"), dict)
        and isinstance(item["app"].get("id"), int)
        and item["app"]["id"] > 0
        and isinstance(item["app"].get("slug"), str)
        and bool(item["app"]["slug"].strip())
    ]
    if not identified_rules:
        return False, "public collection held: enabled deployment protection rule lacks stable App identity"
    return True, (
        f"protected environment {PROTECTED_ENVIRONMENT} is ready for guarded public dispatch "
        f"with {len(identified_rules)} identifiable custom protection rule(s)"
    )


def guarded_public_dispatch_gate(token: str, main_sha: str) -> tuple[bool, str]:
    ready, detail = protected_environment_ready(token)
    if not ready:
        return False, detail
    allowed, reason = ORIGINAL_PUBLIC_DISPATCH_GATE(token, main_sha)
    return allowed, f"{detail}; {reason}"


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
    v4.v3.v2.base.TARGET_REPOSITORY = MIGRATED_TARGET_REPOSITORY
    v4.v3.v2.base.TARGET_REPOSITORY_ID = MIGRATED_TARGET_REPOSITORY_ID
    # Sync/review may proceed, but provider acquisition stays held until GitHub
    # exposes the independently protected acquisition environment as ready.
    v4.v3.v2.should_dispatch_public = guarded_public_dispatch_gate
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
