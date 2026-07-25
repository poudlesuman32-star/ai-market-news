#!/usr/bin/env python3
from __future__ import annotations

import base64
import json
import os
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

API_ROOT = "https://api.github.com"
DEFAULT_TARGET = "spoudel2010-ux/ppi-data-acquisition"
DEFAULT_BASE = "main"
BOOTSTRAP_BRANCH = "agent/bootstrap-r11-public-acquisition"
TEMPLATE_ROOT = Path(__file__).resolve().parents[1] / "bootstrap" / "ppi-data-acquisition"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def api(
    method: str,
    path: str,
    *,
    token: str,
    payload: dict[str, Any] | None = None,
    allowed_statuses: tuple[int, ...] = (200, 201),
) -> tuple[int, Any]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = Request(
        API_ROOT + path,
        data=body,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "PPI public acquisition bootstrap",
            **({"Content-Type": "application/json"} if body is not None else {}),
        },
    )
    try:
        with urlopen(request, timeout=30) as response:
            status = response.status
            raw = response.read()
    except HTTPError as exc:
        status = exc.code
        raw = exc.read()
    parsed: Any = None
    if raw:
        try:
            parsed = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            parsed = raw.decode("utf-8", errors="replace")
    if status not in allowed_statuses:
        message = parsed.get("message") if isinstance(parsed, dict) else str(parsed)
        raise RuntimeError(f"GitHub API {method} {path} returned {status}: {message}")
    return status, parsed


def get_ref_sha(repository: str, branch: str, *, token: str) -> str | None:
    status, payload = api(
        "GET",
        f"/repos/{repository}/git/ref/heads/{quote(branch, safe='')}",
        token=token,
        allowed_statuses=(200, 404, 409),
    )
    if status in {404, 409}:
        return None
    require(isinstance(payload, dict), "Unexpected ref response")
    obj = payload.get("object")
    require(isinstance(obj, dict), "Missing ref object")
    sha = obj.get("sha")
    require(isinstance(sha, str) and len(sha) == 40, "Missing commit SHA")
    return sha


def ensure_repository_initialized(repository: str, *, token: str) -> str:
    main_sha = get_ref_sha(repository, DEFAULT_BASE, token=token)
    if main_sha:
        return main_sha
    placeholder = (
        "# PPI Data Acquisition\n\n"
        "Initialized by a reviewed manual-only cross-repository workflow.\n"
    )
    api(
        "PUT",
        f"/repos/{repository}/contents/README.md",
        token=token,
        payload={
            "message": "Initialize public acquisition repository",
            "content": base64.b64encode(placeholder.encode("utf-8")).decode("ascii"),
            "branch": DEFAULT_BASE,
        },
        allowed_statuses=(201,),
    )
    main_sha = get_ref_sha(repository, DEFAULT_BASE, token=token)
    require(main_sha is not None, "Target initialization did not create main")
    return main_sha


def ensure_branch(repository: str, branch: str, base_sha: str, *, token: str) -> None:
    if get_ref_sha(repository, branch, token=token):
        return
    api(
        "POST",
        f"/repos/{repository}/git/refs",
        token=token,
        payload={"ref": f"refs/heads/{branch}", "sha": base_sha},
        allowed_statuses=(201,),
    )


def read_file_sha(repository: str, path: str, branch: str, *, token: str) -> str | None:
    encoded = quote(path, safe="/")
    status, payload = api(
        "GET",
        f"/repos/{repository}/contents/{encoded}?ref={quote(branch, safe='')}",
        token=token,
        allowed_statuses=(200, 404),
    )
    if status == 404:
        return None
    require(isinstance(payload, dict), f"Unexpected content response for {path}")
    sha = payload.get("sha")
    require(isinstance(sha, str) and sha, f"Missing blob SHA for {path}")
    return sha


def put_file(
    repository: str,
    path: str,
    content: str,
    *,
    branch: str,
    token: str,
) -> None:
    current_sha = read_file_sha(repository, path, branch, token=token)
    payload: dict[str, Any] = {
        "message": f"Bootstrap public acquisition: {path}",
        "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
        "branch": branch,
    }
    if current_sha:
        payload["sha"] = current_sha
    api(
        "PUT",
        f"/repos/{repository}/contents/{quote(path, safe='/')}",
        token=token,
        payload=payload,
    )


def target_files() -> dict[str, str]:
    require(TEMPLATE_ROOT.is_dir(), f"Missing template root: {TEMPLATE_ROOT}")
    result: dict[str, str] = {}
    for path in sorted(TEMPLATE_ROOT.rglob("*")):
        if not path.is_file():
            continue
        require(not path.is_symlink(), f"Template symlink is forbidden: {path}")
        relative = path.relative_to(TEMPLATE_ROOT).as_posix()
        require(relative and not relative.startswith("../"), f"Unsafe template path: {relative}")
        result[relative] = path.read_text(encoding="utf-8")
    required = {
        "README.md",
        ".gitignore",
        ".github/workflows/collect-r11-public-evidence.yml",
        "config/r11_batch_003.json",
        "contracts/PPI-R11-PUBLIC-ACQUISITION-003.json",
        "src/collect_raw_provider_evidence.py",
        "tests/test_public_boundary.py",
    }
    require(set(result) == required, f"Unexpected target template files: {sorted(result)}")
    return result


def ensure_draft_pr(repository: str, *, token: str) -> str:
    owner = repository.split("/", 1)[0]
    _, existing = api(
        "GET",
        f"/repos/{repository}/pulls?state=open&head={quote(owner + ':' + BOOTSTRAP_BRANCH, safe=':')}&base={DEFAULT_BASE}",
        token=token,
    )
    if isinstance(existing, list) and existing:
        url = existing[0].get("html_url")
        require(isinstance(url, str), "Existing PR is missing a URL")
        return url
    _, created = api(
        "POST",
        f"/repos/{repository}/pulls",
        token=token,
        payload={
            "title": "Bootstrap manual-only PPI public data acquisition",
            "head": BOOTSTRAP_BRANCH,
            "base": DEFAULT_BASE,
            "draft": True,
            "body": (
                "## Summary\n"
                "- initialize the dedicated public PPI acquisition boundary\n"
                "- bind the exact frozen batch-3 twelve-ticker and 48-bundle scope\n"
                "- add a manual-only Alpha Vantage and MarketData raw collector\n"
                "- retain provider payload hashes, immutable receipts, and workflow artifacts\n"
                "- keep schedules and private-repository dispatch disabled\n\n"
                "## Safety\n"
                "No private curation, derived calculations, scoring, countability, registry writes, "
                "production, broker, order, trading, MMM/raw_data, or R12 authority is added.\n\n"
                "## Required repository secrets before collection\n"
                "- `PPI_ALPHA_VANTAGE_API_KEY`\n"
                "- `PPI_MARKETDATA_TOKEN`\n"
            ),
        },
        allowed_statuses=(201,),
    )
    require(isinstance(created, dict), "Unexpected PR creation response")
    url = created.get("html_url")
    require(isinstance(url, str), "Created PR is missing a URL")
    return url


def main() -> int:
    token = os.environ.get("PPI_CROSS_REPOSITORY_AUTOMATION", "").strip()
    repository = os.environ.get("TARGET_REPOSITORY", DEFAULT_TARGET).strip()
    require(bool(token), "PPI_CROSS_REPOSITORY_AUTOMATION is not configured")
    require(repository == DEFAULT_TARGET, f"Unexpected target repository: {repository}")

    _, metadata = api("GET", f"/repos/{repository}", token=token)
    require(isinstance(metadata, dict), "Unexpected repository metadata")
    require(metadata.get("visibility") == "public", "Target repository must remain public")
    require(metadata.get("archived") is False, "Target repository is archived")

    base_sha = ensure_repository_initialized(repository, token=token)
    ensure_branch(repository, BOOTSTRAP_BRANCH, base_sha, token=token)
    files = target_files()
    for path, content in files.items():
        put_file(repository, path, content, branch=BOOTSTRAP_BRANCH, token=token)

    pr_url = ensure_draft_pr(repository, token=token)
    result = {
        "status": "bootstrap_pr_ready",
        "repository": repository,
        "branch": BOOTSTRAP_BRANCH,
        "file_count": len(files),
        "pull_request": pr_url,
    }
    print(json.dumps(result, sort_keys=True))
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as summary:
            summary.write("## PPI public acquisition bootstrap\n\n")
            summary.write(f"Draft PR: {pr_url}\n")
            summary.write(f"Files: {len(files)}\n")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"bootstrap failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
