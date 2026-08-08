#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

API_ROOT = "https://api.github.com"
PRIVATE_REPOSITORY = "musksuman3/ai-signal-engine"
PRIVATE_REPOSITORY_ID = 1290626648
WORKFLOW = "ppi-r2-exact-head-validation.yml"
PR_NUMBER = 222


def api(path: str, token: str) -> Any:
    request = Request(
        API_ROOT + path,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "PPI exact-head CI observer",
        },
    )
    try:
        with urlopen(request, timeout=30) as response:
            return json.load(response)
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(f"GitHub API read failed for {path}: {exc}") from exc


def main() -> int:
    token = os.environ.get("RAW_TOKEN", "").strip()
    if not token:
        raise RuntimeError("RAW_TOKEN is not configured")
    repo = api(f"/repos/{PRIVATE_REPOSITORY}", token)
    if int(repo.get("id", 0)) != PRIVATE_REPOSITORY_ID:
        raise RuntimeError("private repository ID drift")
    pr = api(f"/repos/{PRIVATE_REPOSITORY}/pulls/{PR_NUMBER}", token)
    head_sha = str(((pr.get("head") or {}).get("sha") or "")).lower()
    runs = api(
        f"/repos/{PRIVATE_REPOSITORY}/actions/workflows/{WORKFLOW}/runs?branch=main&per_page=10",
        token,
    )
    items = [item for item in runs.get("workflow_runs", []) if isinstance(item, dict)]
    latest = items[0] if items else None
    report = {
        "schema_version": "1.0.0",
        "repository": PRIVATE_REPOSITORY,
        "repository_id": PRIVATE_REPOSITORY_ID,
        "pull_request": PR_NUMBER,
        "current_pr_head_sha": head_sha,
        "workflow": WORKFLOW,
        "run_id": latest.get("id") if latest else None,
        "run_attempt": latest.get("run_attempt") if latest else None,
        "status": latest.get("status") if latest else "not_registered",
        "conclusion": latest.get("conclusion") if latest else None,
        "workflow_head_sha": latest.get("head_sha") if latest else None,
        "authorized_actions": [],
    }
    root = Path(os.environ.get("OUTPUT_ROOT", "runtime/ppi-migration-autopilot"))
    root.mkdir(parents=True, exist_ok=True)
    (root / "r2-exact-head-ci.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
