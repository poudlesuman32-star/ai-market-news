from __future__ import annotations

import argparse
from pathlib import Path

import review_stable_instrument_id_allocation as base

SOURCE_WORKFLOW_PATH = ".github/workflows/ppi-stable-instrument-id-allocation-pilot.yml"
SOURCE_EVENT = "workflow_dispatch"
EXPECTED_REPOSITORY = base.EXPECTED_REPOSITORY


class ReviewError(base.ReviewError):
    pass


def validate_source_run(value: dict, run_id: str, attempt: str) -> dict:
    if not run_id.isdigit() or not attempt.isdigit():
        raise ReviewError("Source run ID and attempt must be decimal integers")
    checks = {
        "id": value.get("id") == int(run_id),
        "attempt": value.get("run_attempt") == int(attempt),
        "workflow_path": value.get("path") == SOURCE_WORKFLOW_PATH,
        "event": value.get("event") == SOURCE_EVENT,
        "repository": (value.get("repository") or {}).get("full_name")
        == EXPECTED_REPOSITORY,
        "main": value.get("head_branch") == "main",
        "completed": value.get("status") == "completed",
        "success": value.get("conclusion") == "success",
    }
    failed = [key for key, ok in checks.items() if not ok]
    if failed:
        raise ReviewError("Source run identity failed: " + ", ".join(failed))
    return checks


def review_artifact(
    *,
    artifact_root: Path,
    source_run_json: Path,
    source_run_id: str,
    source_run_attempt: str,
    contract_path: Path,
) -> dict:
    source_checks = validate_source_run(
        base.read_json(source_run_json), source_run_id, source_run_attempt
    )
    paths = base.files_under(artifact_root)
    if paths == base.BLOCKED_PATHS:
        result = base.validate_blocked(artifact_root)
    elif paths == base.SUCCESS_PATHS:
        result = base.validate_success(
            artifact_root, contract_path, source_run_id, source_run_attempt
        )
    else:
        raise ReviewError("Artifact paths are not exact: " + ", ".join(sorted(paths)))
    return {
        "schema_version": "1.0.0",
        "review_contract_id": base.REVIEW_CONTRACT_ID,
        "source_contract_id": base.SOURCE_CONTRACT_ID,
        "source_repository": EXPECTED_REPOSITORY,
        "source_run_id": int(source_run_id),
        "source_run_attempt": int(source_run_attempt),
        "reviewed_at_utc": base.now(),
        "source_run_checks": source_checks,
        **result,
        "authority": {
            "universe_snapshot_assembly": False,
            "screening": False,
            "deep_evidence_collection": False,
            "private_access": False,
            "private_dispatch": False,
            "billing_budget_mutation": False,
            "registry_mutation": False,
            "production": False,
            "publication": False,
            "trading": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--source-run-json", type=Path, required=True)
    parser.add_argument("--source-run-id", required=True)
    parser.add_argument("--source-run-attempt", required=True)
    parser.add_argument(
        "--contract",
        type=Path,
        default=Path(
            "contracts/PPI-STABLE-INSTRUMENT-ID-ALLOCATION-PILOT-001-R1.json"
        ),
    )
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    try:
        value = review_artifact(
            artifact_root=args.artifact_root,
            source_run_json=args.source_run_json,
            source_run_id=args.source_run_id,
            source_run_attempt=args.source_run_attempt,
            contract_path=args.contract,
        )
        base.write_review(args.output_root, value)
        return 0
    except base.ReviewError as exc:
        base.write_failure(
            args.output_root, str(exc), args.source_run_id, args.source_run_attempt
        )
        raise


if __name__ == "__main__":
    raise SystemExit(main())
