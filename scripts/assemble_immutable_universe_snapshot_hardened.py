from __future__ import annotations

import assemble_immutable_universe_snapshot as base

REVIEW_WORKFLOW_PATH = ".github/workflows/ppi-stable-instrument-id-allocation-artifact-review.yml"
REVIEW_EVENT = "workflow_dispatch"


def validate_run(value: dict, run_id: str, attempt: str) -> dict:
    if not run_id.isdigit() or not attempt.isdigit():
        raise base.SnapshotError("Run ID and attempt must be decimal integers")
    checks = {
        "id": value.get("id") == int(run_id),
        "attempt": value.get("run_attempt") == int(attempt),
        "workflow_path": value.get("path") == REVIEW_WORKFLOW_PATH,
        "event": value.get("event") == REVIEW_EVENT,
        "repository": (value.get("repository") or {}).get("full_name")
        == base.EXPECTED_REPOSITORY,
        "main": value.get("head_branch") == "main",
        "completed": value.get("status") == "completed",
        "success": value.get("conclusion") == "success",
    }
    failed = [key for key, ok in checks.items() if not ok]
    if failed:
        raise base.SnapshotError("Review run identity failed: " + ", ".join(failed))
    return checks


def main() -> int:
    original = base.validate_run
    base.validate_run = validate_run
    try:
        return base.main()
    finally:
        base.validate_run = original


if __name__ == "__main__":
    raise SystemExit(main())
