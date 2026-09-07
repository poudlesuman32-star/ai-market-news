from __future__ import annotations

import review_immutable_universe_snapshot as base

SOURCE_WORKFLOW_PATH = ".github/workflows/ppi-immutable-universe-snapshot-pilot.yml"
SOURCE_EVENT = "workflow_dispatch"


def validate_source_run(value: dict, run_id: str, attempt: str) -> dict:
    if not run_id.isdigit() or not attempt.isdigit():
        raise base.ReviewError("Source run ID and attempt must be decimal integers")
    checks = {
        "id": value.get("id") == int(run_id),
        "attempt": value.get("run_attempt") == int(attempt),
        "workflow_path": value.get("path") == SOURCE_WORKFLOW_PATH,
        "event": value.get("event") == SOURCE_EVENT,
        "repository": (value.get("repository") or {}).get("full_name")
        == base.EXPECTED_REPOSITORY,
        "main": value.get("head_branch") == "main",
        "completed": value.get("status") == "completed",
        "success": value.get("conclusion") == "success",
    }
    failed = [key for key, ok in checks.items() if not ok]
    if failed:
        raise base.ReviewError("Source run identity failed: " + ", ".join(failed))
    return checks


base.validate_source_run = validate_source_run


if __name__ == "__main__":
    raise SystemExit(base.main())
