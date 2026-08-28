from __future__ import annotations

import argparse
import json
from pathlib import Path

CONTRACT_PATH = Path("contracts/PPI-PUBLIC-FIRST-BLOCKER-REMEDIATION-001-R1.json")


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
