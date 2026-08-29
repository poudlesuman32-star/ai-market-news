from __future__ import annotations

import argparse
import json
from pathlib import Path

CONTRACT_PATH = Path("contracts/PPI-PUBLIC-FIRST-BLOCKER-REMEDIATION-001-R1.json")
REPORT_FIELDS = {
    "blocker_class",
    "canonical_step",
    "evidence",
    "safe_actions_taken",
    "approval_required_for",
    "next_safe_action",
}


class PolicyError(RuntimeError):
    pass


def load_contract(path: Path = CONTRACT_PATH) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    required = {
        "schema_version",
        "contract_id",
        "canonical_backlog",
        "status_ledger",
        "blocker_classes",
        "globally_prohibited_without_explicit_approval",
        "safe_preparation_actions",
        "progress_report_schema",
        "anti_loop",
        "authority",
    }
    if set(value) != required:
        raise PolicyError("blocker remediation contract fields differ from frozen shape")
    if value["contract_id"] != "PPI-PUBLIC-FIRST-BLOCKER-REMEDIATION-001-R1":
        raise PolicyError("unexpected blocker remediation contract id")
    return value


def classify(blocker_class: str, requested_action: str | None, *, contract: dict) -> dict:
    classes = contract["blocker_classes"]
    if blocker_class not in classes:
        raise PolicyError(f"unknown blocker class: {blocker_class}")

    policy = classes[blocker_class]
    safe_actions = set(policy["safe_actions"])
    approval_actions = set(policy["approval_required_actions"])
    global_approval = set(contract["globally_prohibited_without_explicit_approval"])

    if requested_action is None:
        return {
            "blocker_class": blocker_class,
            "decision": "classify_only",
            "safe_actions": sorted(safe_actions),
            "approval_required_actions": sorted(approval_actions),
        }

    if requested_action in global_approval or requested_action in approval_actions:
        return {
            "blocker_class": blocker_class,
            "requested_action": requested_action,
            "decision": "stop_for_explicit_approval",
            "allowed": False,
        }

    if requested_action in safe_actions and requested_action in contract["safe_preparation_actions"]:
        return {
            "blocker_class": blocker_class,
            "requested_action": requested_action,
            "decision": "safe_preparation_allowed",
            "allowed": True,
        }

    return {
        "blocker_class": blocker_class,
        "requested_action": requested_action,
        "decision": "not_allowlisted",
        "allowed": False,
    }


def validate_progress_report(report: dict, *, contract: dict) -> None:
    schema = contract["progress_report_schema"]
    required = set(schema["required_fields"])
    if required != REPORT_FIELDS or set(report) != REPORT_FIELDS:
        raise PolicyError("progress report fields differ from frozen shape")

    blocker_class = report["blocker_class"]
    if not isinstance(blocker_class, str) or not blocker_class.strip():
        raise PolicyError("blocker_class must be a non-empty string")
    if blocker_class not in contract["blocker_classes"]:
        raise PolicyError("progress report uses unknown blocker class")

    step = report["canonical_step"]
    if isinstance(step, bool) or not isinstance(step, int):
        raise PolicyError("canonical_step must be an integer")
    if not schema["canonical_step_min"] <= step <= schema["canonical_step_max"]:
        raise PolicyError("canonical_step is outside the canonical 26-step backlog")

    for field in schema["array_fields"]:
        value = report[field]
        if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
            raise PolicyError(f"{field} must be an array of non-empty strings")

    next_safe_action = report["next_safe_action"]
    if not isinstance(next_safe_action, str) or not next_safe_action.strip():
        raise PolicyError("next_safe_action must be a non-empty string")

    safe_taken = set(report["safe_actions_taken"])
    safe_global = set(contract["safe_preparation_actions"])
    if not safe_taken <= safe_global:
        raise PolicyError("safe_actions_taken contains an action outside the global safe allowlist")
    safe_for_class = set(contract["blocker_classes"][blocker_class]["safe_actions"])
    if not safe_taken <= safe_for_class:
        raise PolicyError("safe_actions_taken contains an action not allowlisted for blocker_class")

    approval_global = set(contract["globally_prohibited_without_explicit_approval"])
    if not set(report["approval_required_for"]) <= approval_global:
        raise PolicyError("approval_required_for contains an action outside the approval fence")

    if not report["evidence"] and not report["safe_actions_taken"]:
        if next_safe_action != schema["no_progress_next_safe_action"]:
            raise PolicyError("report without new evidence or safe action must use no_new_safe_progress")


def build_progress_report(
    *,
    blocker_class: str,
    canonical_step: int,
    evidence: list[str],
    safe_actions_taken: list[str],
    approval_required_for: list[str],
    next_safe_action: str,
    contract: dict,
) -> dict:
    report = {
        "blocker_class": blocker_class,
        "canonical_step": canonical_step,
        "evidence": list(evidence),
        "safe_actions_taken": list(safe_actions_taken),
        "approval_required_for": list(approval_required_for),
        "next_safe_action": next_safe_action,
    }
    validate_progress_report(report, contract=contract)
    return report


def validate_contract(contract: dict) -> None:
    global_approval = set(contract["globally_prohibited_without_explicit_approval"])
    safe_global = set(contract["safe_preparation_actions"])
    if global_approval & safe_global:
        raise PolicyError("approval-required and safe-preparation action sets overlap")

    for name, policy in contract["blocker_classes"].items():
        safe = set(policy.get("safe_actions", []))
        approval = set(policy.get("approval_required_actions", []))
        if safe & approval:
            raise PolicyError(f"{name}: safe and approval-required actions overlap")
        if not safe <= safe_global:
            raise PolicyError(f"{name}: class contains non-global safe action")
        if not approval <= global_approval:
            raise PolicyError(f"{name}: class contains non-global approval action")

    report_schema = contract["progress_report_schema"]
    expected_report_schema = {
        "required_fields": [
            "blocker_class",
            "canonical_step",
            "evidence",
            "safe_actions_taken",
            "approval_required_for",
            "next_safe_action",
        ],
        "canonical_step_min": 1,
        "canonical_step_max": 26,
        "array_fields": ["evidence", "safe_actions_taken", "approval_required_for"],
        "nonempty_string_fields": ["blocker_class", "next_safe_action"],
        "no_progress_next_safe_action": "no_new_safe_progress",
    }
    if report_schema != expected_report_schema:
        raise PolicyError("progress report schema differs from frozen requirements")

    authority = contract["authority"]
    if any(authority.values()):
        raise PolicyError("blocker remediation contract must grant zero execution authority")

    anti_loop = contract["anti_loop"]
    if anti_loop != {
        "require_new_evidence_or_safe_change": True,
        "duplicate_prs_for_same_blocker_forbidden": True,
        "no_progress_status": "no_new_safe_progress",
    }:
        raise PolicyError("anti-loop policy differs from frozen requirements")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("blocker_class")
    parser.add_argument("requested_action", nargs="?")
    parser.add_argument("--contract", type=Path, default=CONTRACT_PATH)
    args = parser.parse_args()

    contract = load_contract(args.contract)
    validate_contract(contract)
    print(json.dumps(classify(args.blocker_class, args.requested_action, contract=contract), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
