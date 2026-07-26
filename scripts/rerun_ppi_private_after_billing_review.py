#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

API_ROOT = "https://api.github.com"
CONFIRMATION = "RECOVER-PPI-PRIVATE-AFTER-BILLING-REVIEW"
PRIVATE_REPOSITORY = "musksuman3/ai-signal-engine"
PRIVATE_REPOSITORY_ID = 1290626648
RECOVERY_RUN_ID = 30188784601
EXPECTED_PRIVATE_HEAD_SHA = "49cbb0ce6aaa9bdb2e63dc54ac443a2b5cf6b312"


class RecoveryError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RecoveryError(message)


def api(
    method: str,
    path: str,
    *,
    token: str,
    payload: dict[str, Any] | None = None,
    allowed_statuses: tuple[int, ...] = (200,),
) -> tuple[int, Any]:
    body = None if payload is None else json.dumps(payload, sort_keys=True).encode("utf-8")
    request = Request(
        API_ROOT + path,
        data=body,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "PPI manual private recovery after billing review",
            **({"Content-Type": "application/json"} if body is not None else {}),
        },
    )
    try:
        with urlopen(request, timeout=30) as response:
            status = int(response.status)
            raw = response.read()
    except HTTPError as exc:
        status = int(exc.code)
        raw = exc.read()
    except (URLError, TimeoutError, OSError) as exc:
        raise RecoveryError(f"GitHub API network failure for {method} {path}: {exc}") from exc
    try:
        value: Any = json.loads(raw.decode("utf-8")) if raw else None
    except (UnicodeDecodeError, json.JSONDecodeError):
        value = raw.decode("utf-8", errors="replace")
    if status not in allowed_statuses:
        detail = value.get("message") if isinstance(value, dict) else value
        raise RecoveryError(f"GitHub API {method} {path} returned {status}: {detail}")
    return status, value


def main() -> int:
    token = os.environ.get("RAW_TOKEN", "").strip()
    confirmation = os.environ.get("RECOVERY_CONFIRMATION", "").strip()
    require(token, "RAW_TOKEN is not configured")
    require(confirmation == CONFIRMATION, "billing-review recovery confirmation is invalid")

    _, repository = api("GET", f"/repos/{PRIVATE_REPOSITORY}", token=token)
    require(isinstance(repository, dict), "private repository response is invalid")
    require(int(repository.get("id", 0)) == PRIVATE_REPOSITORY_ID, "private repository ID drift")
    require(repository.get("private") is True and repository.get("archived") is False, "private repository boundary mismatch")

    _, run = api("GET", f"/repos/{PRIVATE_REPOSITORY}/actions/runs/{RECOVERY_RUN_ID}", token=token)
    require(isinstance(run, dict), "recovery run response is invalid")
    require(str(run.get("head_sha") or "").lower() == EXPECTED_PRIVATE_HEAD_SHA, "recovery run private SHA mismatch")
    require(run.get("event") == "workflow_dispatch", "recovery run event mismatch")
    require(run.get("head_branch") == "main", "recovery run branch mismatch")
    require(run.get("status") == "completed" and run.get("conclusion") == "failure", "recovery run is not the expected failed run")

    status, jobs = api(
        "GET",
        f"/repos/{PRIVATE_REPOSITORY}/actions/runs/{RECOVERY_RUN_ID}/jobs?filter=latest&per_page=100",
        token=token,
    )
    require(status == 200 and isinstance(jobs, dict) and isinstance(jobs.get("jobs"), list), "recovery run jobs response is invalid")
    job_items = [item for item in jobs["jobs"] if isinstance(item, dict)]
    require(len(job_items) == 1, "recovery run must contain exactly one job")
    steps = job_items[0].get("steps") if isinstance(job_items[0].get("steps"), list) else []
    require(not steps, "recovery run already executed workflow steps; automatic rerun is forbidden")
    require(not job_items[0].get("runner_id") and not job_items[0].get("runner_name"), "recovery job already received a runner; automatic rerun is forbidden")

    api(
        "PUT",
        f"/repos/{PRIVATE_REPOSITORY}/actions/permissions",
        token=token,
        payload={"enabled": True, "allowed_actions": "selected"},
        allowed_statuses=(204,),
    )
    api(
        "PUT",
        f"/repos/{PRIVATE_REPOSITORY}/actions/permissions/selected-actions",
        token=token,
        payload={
            "github_owned_allowed": True,
            "verified_allowed": False,
            "patterns_allowed": [],
        },
        allowed_statuses=(204,),
    )

    _, permissions = api("GET", f"/repos/{PRIVATE_REPOSITORY}/actions/permissions", token=token)
    require(isinstance(permissions, dict), "private Actions permissions response is invalid")
    require(permissions.get("enabled") is True and permissions.get("allowed_actions") == "selected", "private Actions selected-only policy is not active")

    api(
        "POST",
        f"/repos/{PRIVATE_REPOSITORY}/actions/runs/{RECOVERY_RUN_ID}/rerun-failed-jobs",
        token=token,
        allowed_statuses=(201, 202),
    )

    for attempt in range(25):
        _, current = api("GET", f"/repos/{PRIVATE_REPOSITORY}/actions/runs/{RECOVERY_RUN_ID}", token=token)
        require(isinstance(current, dict), "recovery run poll response is invalid")
        run_attempt = int(current.get("run_attempt") or 1)
        status_value = str(current.get("status") or "")
        if run_attempt >= 2 and status_value in {"queued", "pending", "waiting", "requested", "in_progress", "completed"}:
            print(json.dumps({
                "status": "recovery_rerun_accepted",
                "recovery_run_id": RECOVERY_RUN_ID,
                "run_attempt": run_attempt,
                "run_status": status_value,
                "run_conclusion": current.get("conclusion"),
                "private_head_sha": EXPECTED_PRIVATE_HEAD_SHA,
            }, sort_keys=True))
            return 0
        if attempt < 24:
            time.sleep(5)
    raise RecoveryError("private recovery rerun was not visible after 120 seconds")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RecoveryError as exc:
        raise SystemExit(str(exc)) from exc
