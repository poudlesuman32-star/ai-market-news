#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess
import sys

import ppi_migration_autopilot_v2 as v2


def run_bootstrap_r2(token: str) -> None:
    v2.base.run_command(
        [sys.executable, "scripts/bootstrap_ppi_data_acquisition_r2.py"],
        env={
            "PPI_CROSS_REPOSITORY_AUTOMATION": token,
            "TARGET_REPOSITORY": v2.base.TARGET_REPOSITORY,
        },
    )


def latest_successful_current_public_run(token: str):
    main_sha = v2.target_main_sha(token).lower()
    runs = v2.base.list_workflow_runs(v2.base.TARGET_REPOSITORY, v2.base.PUBLIC_WORKFLOW, token)
    for run in runs:
        if (
            run.get("status") == "completed"
            and run.get("conclusion") == "success"
            and str(run.get("head_sha", "")).lower() == main_sha
        ):
            return run
    return None


def main() -> int:
    v2.base.run_bootstrap = run_bootstrap_r2
    v2.base.latest_successful_public_run = latest_successful_current_public_run
    return v2.main()


if __name__ == "__main__":
    raise SystemExit(main())
