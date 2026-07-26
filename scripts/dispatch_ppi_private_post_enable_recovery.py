#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

API_ROOT = "https://api.github.com"
PUBLIC_REPOSITORY = "spoudel2010-ux/ppi-data-acquisition"
PUBLIC_REPOSITORY_ID = 1312286476
PUBLIC_RUN_ID = 30185438920
PUBLIC_WORKFLOW_PATH = ".github/workflows/collect-r11-public-evidence.yml"
PRIVATE_REPOSITORY = "musksuman3/ai-signal-engine"
PRIVATE_REPOSITORY_ID = 1290626648
PRIVATE_WORKFLOW = "ppi-r11-private-final-analysis.yml"
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
            "User-Agent": "PPI exact post-enable recovery dispatch",
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


def verify_repository(name: str, expected_id: int, *, token: str, private: bool) -> dict[str, Any]:
    _, value = api("GET", f"/repos/{name}", token=token)
    require(isinstance(value, dict), f"repository response is invalid: {name}")
    require(int(value.get("id", 0)) == expected_id, f"repository ID drift: {name}")
    require(value.get("private") is private, f"repository visibility drift: {name}")
    require(value.get("archived") is False, f"repository is archived: {name}")
    return value


def private_runs(token: str) -> list[dict[str, Any]]:
    _, value = api(
        "GET",
        f"/repos/{PRIVATE_REPOSITORY}/actions/workflows/{PRIVATE_WORKFLOW}/runs?event=workflow_dispatch&per_page=50",
        token=token,
    )
    require(isinstance(value, dict) and isinstance(value.get("workflow_runs"), list), "private workflow runs response is invalid")
    return [item for item in value["workflow_runs"] if isinstance(item, dict)]


def main() -> int:
    token = os.environ.get("RAW_TOKEN", "").strip()
    require(token, "RAW_TOKEN is not configured")

    verify_repository(PUBLIC_REPOSITORY, PUBLIC_REPOSITORY_ID, token=token, private=False)
    verify_repository(PRIVATE_REPOSITORY, PRIVATE_REPOSITORY_ID, token=token, private=True)

    _, public_run = api("GET", f"/repos/{PUBLIC_REPOSITORY}/actions/runs/{PUBLIC_RUN_ID}", token=token)
    require(isinstance(public_run, dict), "public run response is invalid")
    require(public_run.get("status") == "completed", "public run is not completed")
    require(public_run.get("conclusion") == "success", "public run did not succeed")
    require(public_run.get("path") == PUBLIC_WORKFLOW_PATH, "public run workflow path mismatch")
    public_head_sha = str(public_run.get("head_sha") or "").lower()
    require(len(public_head_sha) == 40 and all(char in "0123456789abcdef" for char in public_head_sha), "public head SHA is invalid")

    _, private_ref = api("GET", f"/repos/{PRIVATE_REPOSITORY}/git/ref/heads/main", token=token)
    require(isinstance(private_ref, dict), "private main ref response is invalid")
    private_head_sha = str((private_ref.get("object") or {}).get("sha") or "").lower()
    require(private_head_sha == EXPECTED_PRIVATE_HEAD_SHA, "private main moved outside the reviewed recovery SHA")

    _, permissions = api("GET", f"/repos/{PRIVATE_REPOSITORY}/actions/permissions", token=token)
    require(isinstance(permissions, dict), "private Actions permissions response is invalid")
    require(permissions.get("enabled") is True, "private Actions are not enabled")
    require(permissions.get("allowed_actions") == "selected", "private Actions policy is not selected-only")

    runs_before = private_runs(token)
    current_sha_runs = [run for run in runs_before if str(run.get("head_sha") or "").lower() == EXPECTED_PRIVATE_HEAD_SHA]
    if current_sha_runs:
        newest = sorted(current_sha_runs, key=lambda item: str(item.get("created_at") or ""), reverse=True)[0]
        print(json.dumps({
            "status": "recovery_already_exists",
            "private_run_id": newest.get("id"),
            "private_run_status": newest.get("status"),
            "private_run_conclusion": newest.get("conclusion"),
            "private_head_sha": EXPECTED_PRIVATE_HEAD_SHA,
            "public_run_id": PUBLIC_RUN_ID,
        }, sort_keys=True))
        return 0

    api(
        "POST",
        f"/repos/{PRIVATE_REPOSITORY}/actions/workflows/{PRIVATE_WORKFLOW}/dispatches",
        token=token,
        payload={
            "ref": "main",
            "inputs": {
                "public_run_id": str(PUBLIC_RUN_ID),
                "public_head_sha": public_head_sha,
            },
        },
        allowed_statuses=(204,),
    )

    for attempt in range(13):
        runs_after = private_runs(token)
        recovery = next(
            (run for run in runs_after if str(run.get("head_sha") or "").lower() == EXPECTED_PRIVATE_HEAD_SHA),
            None,
        )
        if recovery is not None:
            print(json.dumps({
                "status": "recovery_dispatched",
                "private_run_id": recovery.get("id"),
                "private_run_status": recovery.get("status"),
                "private_run_conclusion": recovery.get("conclusion"),
                "private_head_sha": EXPECTED_PRIVATE_HEAD_SHA,
                "public_run_id": PUBLIC_RUN_ID,
                "public_head_sha": public_head_sha,
            }, sort_keys=True))
            return 0
        if attempt < 12:
            time.sleep(5)
    raise RecoveryError("post-enable private recovery run was not visible after 60 seconds")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RecoveryError as exc:
        raise SystemExit(str(exc)) from exc
