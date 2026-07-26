#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

API_ROOT = "https://api.github.com"
PRIVATE_REPOSITORY = "musksuman3/ai-signal-engine"
PRIVATE_REPOSITORY_ID = 1290626648
RECOVERY_RUN_ID = 30188784601
EXPECTED_PRIVATE_HEAD_SHA = "49cbb0ce6aaa9bdb2e63dc54ac443a2b5cf6b312"


class HoldError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise HoldError(message)


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
            "User-Agent": "PPI fail-closed private Actions hold",
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
        raise HoldError(f"GitHub API network failure for {method} {path}: {exc}") from exc
    try:
        value: Any = json.loads(raw.decode("utf-8")) if raw else None
    except (UnicodeDecodeError, json.JSONDecodeError):
        value = raw.decode("utf-8", errors="replace")
    if status not in allowed_statuses:
        detail = value.get("message") if isinstance(value, dict) else value
        raise HoldError(f"GitHub API {method} {path} returned {status}: {detail}")
    return status, value


def main() -> int:
    token = os.environ.get("RAW_TOKEN", "").strip()
    require(token, "RAW_TOKEN is not configured")

    _, repository = api("GET", f"/repos/{PRIVATE_REPOSITORY}", token=token)
    require(isinstance(repository, dict), "private repository response is invalid")
    require(int(repository.get("id", 0)) == PRIVATE_REPOSITORY_ID, "private repository ID drift")
    require(repository.get("private") is True and repository.get("archived") is False, "private repository boundary mismatch")

    _, run = api("GET", f"/repos/{PRIVATE_REPOSITORY}/actions/runs/{RECOVERY_RUN_ID}", token=token)
    require(isinstance(run, dict), "recovery run response is invalid")
    require(str(run.get("head_sha") or "").lower() == EXPECTED_PRIVATE_HEAD_SHA, "recovery run private SHA mismatch")
    status = str(run.get("status") or "")
    conclusion = run.get("conclusion")
    attempt = int(run.get("run_attempt") or 1)

    if status in {"queued", "pending", "waiting", "requested", "in_progress"}:
        print(json.dumps({
            "status": "hold_not_applied_recovery_active",
            "recovery_run_id": RECOVERY_RUN_ID,
            "run_status": status,
            "run_attempt": attempt,
        }, sort_keys=True))
        return 0
    if status == "completed" and conclusion == "success":
        print(json.dumps({
            "status": "hold_not_applied_recovery_succeeded",
            "recovery_run_id": RECOVERY_RUN_ID,
            "run_attempt": attempt,
        }, sort_keys=True))
        return 0

    require(status == "completed" and conclusion == "failure", "recovery run is not the expected terminal failure")

    _, permissions = api("GET", f"/repos/{PRIVATE_REPOSITORY}/actions/permissions", token=token)
    require(isinstance(permissions, dict), "private Actions permissions response is invalid")
    if permissions.get("enabled") is not False:
        api(
            "PUT",
            f"/repos/{PRIVATE_REPOSITORY}/actions/permissions",
            token=token,
            payload={"enabled": False},
            allowed_statuses=(204,),
        )

    _, after = api("GET", f"/repos/{PRIVATE_REPOSITORY}/actions/permissions", token=token)
    require(isinstance(after, dict) and after.get("enabled") is False, "private Actions fail-closed hold was not applied")
    print(json.dumps({
        "status": "private_actions_held_after_pre_runner_failure",
        "repository": PRIVATE_REPOSITORY,
        "recovery_run_id": RECOVERY_RUN_ID,
        "run_attempt": attempt,
        "run_conclusion": conclusion,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except HoldError as exc:
        raise SystemExit(str(exc)) from exc
