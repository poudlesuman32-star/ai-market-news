#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

API_ROOT = "https://api.github.com"
TARGET_REPOSITORY = "MarketMakingLFG/ppi-data-acquisition"
TARGET_REPOSITORY_ID = 1312286476
TARGET_BRANCH = "agent/bootstrap-r11-public-acquisition"
BASE_BRANCH = "main"
EXPECTED_PATHS = (
    "README.md",
    ".gitignore",
    ".github/workflows/collect-r11-public-evidence.yml",
    "config/r11_batch_003.json",
    "config/provider_licensing_dispositions.json",
    "contracts/PPI-R11-PUBLIC-ACQUISITION-003.json",
    "contracts/PPI-R11-PUBLIC-ACQUISITION-003-R1.json",
    "contracts/PPI-R11-PUBLIC-ACQUISITION-003-R2.json",
    "contracts/PPI-PUBLIC-COLLECTOR-003-R1.json",
    "contracts/PPI-PUBLIC-COLLECTOR-003-R2.json",
    "src/collect_raw_provider_evidence.py",
    "src/collect_raw_provider_evidence_r2.py",
    "src/fetch_yfinance_expectations.py",
    "src/publish_private_handoff.py",
    "tests/test_public_boundary.py",
)


class PrepareError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise PrepareError(message)


def api(
    method: str,
    path: str,
    *,
    token: str,
    payload: dict[str, Any] | None = None,
    allowed: tuple[int, ...] = (200,),
) -> tuple[int, Any]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = Request(
        API_ROOT + path,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "PPI target update branch preparer",
            **({"Content-Type": "application/json"} if data is not None else {}),
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
        raise PrepareError(f"GitHub API network failure: {exc}") from exc
    value: Any = None
    if raw:
        try:
            value = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            value = raw.decode("utf-8", errors="replace")
    if status not in allowed:
        detail = value.get("message") if isinstance(value, dict) else value
        raise PrepareError(f"GitHub API {method} {path} returned {status}: {detail}")
    return status, value


def blob_sha(path: str, ref: str, token: str) -> str | None:
    status, value = api(
        "GET",
        f"/repos/{TARGET_REPOSITORY}/contents/{quote(path, safe='/')}?ref={quote(ref, safe='')}",
        token=token,
        allowed=(200, 404),
    )
    if status == 404:
        return None
    require(isinstance(value, dict), f"invalid content response for {path}@{ref}")
    sha = value.get("sha")
    require(isinstance(sha, str) and sha, f"missing blob SHA for {path}@{ref}")
    return sha


def ref_sha(ref: str, token: str) -> str:
    _, value = api(
        "GET",
        f"/repos/{TARGET_REPOSITORY}/git/ref/heads/{quote(ref, safe='')}",
        token=token,
    )
    require(isinstance(value, dict), f"invalid ref response for {ref}")
    sha = (value.get("object") or {}).get("sha")
    require(isinstance(sha, str) and len(sha) == 40, f"invalid commit SHA for {ref}")
    return sha


def main() -> int:
    token = os.environ.get("RAW_TOKEN", "").strip()
    require(token, "RAW_TOKEN is not configured")

    _, repository = api("GET", f"/repos/{TARGET_REPOSITORY}", token=token)
    require(isinstance(repository, dict), "invalid target repository response")
    require(int(repository.get("id", 0)) == TARGET_REPOSITORY_ID, "target repository ID drift")
    require(repository.get("visibility") == "public" and repository.get("archived") is False, "target repository boundary mismatch")

    owner = TARGET_REPOSITORY.split("/", 1)[0]
    _, pulls = api(
        "GET",
        f"/repos/{TARGET_REPOSITORY}/pulls?state=open&head={quote(owner + ':' + TARGET_BRANCH, safe=':')}&base={BASE_BRANCH}",
        token=token,
    )
    require(isinstance(pulls, list), "invalid open pull request response")
    require(len(pulls) <= 1, "multiple open target update pull requests exist")

    if not pulls:
        print(json.dumps({"status": "no_open_target_update", "branch": TARGET_BRANCH}, sort_keys=True))
        return 0

    pr = pulls[0]
    pr_number = int(pr.get("number", 0) or 0)
    require(pr_number > 0, "invalid target pull request number")

    differences = []
    for path in EXPECTED_PATHS:
        if blob_sha(path, BASE_BRANCH, token) != blob_sha(path, TARGET_BRANCH, token):
            differences.append(path)
    if differences:
        print(json.dumps({"status": "open_target_update_has_content_changes", "pull_request": pr_number, "changed_paths": differences}, sort_keys=True))
        return 0

    api(
        "PATCH",
        f"/repos/{TARGET_REPOSITORY}/pulls/{pr_number}",
        token=token,
        payload={
            "state": "closed",
            "title": "Superseded no-diff bootstrap update after squash merge",
            "body": "Closed automatically because every reviewed target blob is identical to current `main`. The bootstrap branch is reset before the next real update.",
        },
    )
    main_sha = ref_sha(BASE_BRANCH, token)
    api(
        "PATCH",
        f"/repos/{TARGET_REPOSITORY}/git/refs/heads/{quote(TARGET_BRANCH, safe='')}",
        token=token,
        payload={"sha": main_sha, "force": True},
    )
    print(json.dumps({"status": "closed_no_diff_pr_and_reset_branch", "pull_request": pr_number, "main_sha": main_sha}, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except PrepareError as exc:
        raise SystemExit(str(exc)) from exc
