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


class EnablementError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise EnablementError(message)


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
            "User-Agent": "PPI one-time private Actions enablement",
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
        raise EnablementError(f"GitHub API network failure for {method} {path}: {exc}") from exc
    try:
        value: Any = json.loads(raw.decode("utf-8")) if raw else None
    except (UnicodeDecodeError, json.JSONDecodeError):
        value = raw.decode("utf-8", errors="replace")
    if status not in allowed_statuses:
        detail = value.get("message") if isinstance(value, dict) else value
        raise EnablementError(f"GitHub API {method} {path} returned {status}: {detail}")
    return status, value


def main() -> int:
    token = os.environ.get("RAW_TOKEN", "").strip()
    require(token, "RAW_TOKEN is not configured")

    _, repository = api("GET", f"/repos/{PRIVATE_REPOSITORY}", token=token)
    require(isinstance(repository, dict), "private repository response is invalid")
    require(int(repository.get("id", 0)) == PRIVATE_REPOSITORY_ID, "private repository ID drift")
    require(repository.get("private") is True and repository.get("archived") is False, "private repository boundary mismatch")

    _, before = api("GET", f"/repos/{PRIVATE_REPOSITORY}/actions/permissions", token=token)
    require(isinstance(before, dict), "private Actions permissions response is invalid")

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

    _, after = api("GET", f"/repos/{PRIVATE_REPOSITORY}/actions/permissions", token=token)
    require(isinstance(after, dict), "private Actions verification response is invalid")
    require(after.get("enabled") is True, "private Actions were not enabled")
    require(after.get("allowed_actions") == "selected", "private Actions policy is not selected-only")

    _, selected = api("GET", f"/repos/{PRIVATE_REPOSITORY}/actions/permissions/selected-actions", token=token)
    require(isinstance(selected, dict), "selected Actions verification response is invalid")
    require(selected.get("github_owned_allowed") is True, "GitHub-owned actions are not enabled")
    require(selected.get("verified_allowed") is False, "verified third-party actions must remain disabled")
    require(selected.get("patterns_allowed") in ([], None), "custom action patterns must remain empty")

    print(json.dumps({
        "status": "private_actions_enabled_selected_only",
        "repository": PRIVATE_REPOSITORY,
        "previously_enabled": before.get("enabled"),
        "allowed_actions": after.get("allowed_actions"),
        "github_owned_allowed": selected.get("github_owned_allowed"),
        "verified_allowed": selected.get("verified_allowed"),
        "patterns_allowed": selected.get("patterns_allowed") or [],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except EnablementError as exc:
        raise SystemExit(str(exc)) from exc
