#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import os
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

API_ROOT = "https://api.github.com"
PLAN = Path("docs/architecture/PPI_THREE_REPOSITORY_ARCHITECTURE_AND_MIGRATION_PLAN.md")
BOOTSTRAP_README = Path("bootstrap/ppi-data-acquisition/README.md")
BOOTSTRAP_WORKFLOW = Path(".github/workflows/bootstrap-ppi-data-acquisition.yml")
TARGET_WORKFLOW = Path("bootstrap/ppi-data-acquisition/.github/workflows/collect-r11-public-evidence.yml")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def github_get(path: str) -> tuple[int, Any]:
    request = Request(
        API_ROOT + path,
        method="GET",
        headers={
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "PPI public migration scheduler",
        },
    )
    try:
        with urlopen(request, timeout=20) as response:
            status = int(response.status)
            raw = response.read()
    except HTTPError as exc:
        status = int(exc.code)
        raw = exc.read()
    except (URLError, TimeoutError, OSError) as exc:
        return 0, {"message": f"network_error: {exc}"}
    try:
        return status, json.loads(raw.decode("utf-8")) if raw else None
    except (UnicodeDecodeError, json.JSONDecodeError):
        return status, {"message": raw.decode("utf-8", errors="replace")}


def public_file(repository: str, path: str, ref: str) -> tuple[int, str]:
    status, value = github_get(
        f"/repos/{repository}/contents/{quote(path, safe='/')}?ref={quote(ref, safe='')}"
    )
    if status != 200 or not isinstance(value, dict):
        detail = value.get("message") if isinstance(value, dict) else value
        return status, f"GitHub API returned {status}: {detail}"
    if value.get("encoding") != "base64" or not isinstance(value.get("content"), str):
        return status, "Unexpected contents response"
    try:
        return status, base64.b64decode(value["content"]).decode("utf-8")
    except (ValueError, UnicodeDecodeError) as exc:
        return status, f"Could not decode contents response: {exc}"


def check(name: str, passed: bool, pass_detail: str, blocked_detail: str) -> dict[str, str]:
    return {
        "name": name,
        "status": "pass" if passed else "blocked",
        "detail": pass_detail if passed else blocked_detail,
    }


def build(config: dict[str, Any]) -> dict[str, Any]:
    require(config["schema_version"] == "1.0.0", "unexpected scheduler schema")
    require(config["enabled"] is True, "scheduler is disabled")
    require(config["phase"] == "gate-0-public-readiness", "only gate 0 is authorized")
    require(config["active_task_id"] == "T01", "only T01 is authorized")
    require([item["id"] for item in config["tasks"] if item["status"] == "active"] == ["T01"], "exactly T01 must be active")
    require(config["authority"]["authorized_actions"] == [], "scheduler grants downstream authority")
    for key, value in config["authority"].items():
        if key != "authorized_actions":
            require(value is False, f"scheduler unexpectedly authorizes {key}")

    plan = PLAN.read_text(encoding="utf-8")
    bootstrap_readme = BOOTSTRAP_README.read_text(encoding="utf-8")
    bootstrap_workflow = BOOTSTRAP_WORKFLOW.read_text(encoding="utf-8")
    target_workflow = TARGET_WORKFLOW.read_text(encoding="utf-8")
    checks: list[dict[str, str]] = []

    checks.append(check(
        "canonical_plan",
        "Decision document • Version 1.2" in plan and "Implementation status:** blocked" in plan,
        "Canonical Version 1.2 plan is present and remains fail-closed.",
        "Canonical plan is missing Version 1.2 or the blocked implementation status.",
    ))
    checks.append(check(
        "stable_repository_ids",
        all(str(value) in plan for value in (1290414659, 1312286476, 1290626648)),
        "All stable repository IDs are present.",
        "One or more stable repository IDs are missing.",
    ))
    checks.append(check(
        "hardened_bootstrap_readme",
        all(marker in bootstrap_readme for marker in (
            "Repository ID: `1312286476`",
            "exactly 50 retained paths",
            "PPI-R11-PUBLIC-ACQUISITION-003-R1",
            "public_storage_prohibited",
            "no external network",
            "Do not merge the bootstrap PR until",
        )),
        "Bootstrap README contains the hardened Version 1.2 boundary.",
        "Bootstrap README is missing one or more required markers.",
    ))
    checks.append(check(
        "bootstrap_manual_only",
        "\n  workflow_dispatch:\n" in bootstrap_workflow
        and "\n  schedule:\n" not in bootstrap_workflow
        and "\n  repository_dispatch:\n" not in bootstrap_workflow
        and "spoudel2010-ux/ppi-data-acquisition" in bootstrap_workflow
        and "secrets.RAW_TOKEN" in bootstrap_workflow,
        "Bootstrap is manual-only and exact-target.",
        "Bootstrap trigger, target, or token binding drifted.",
    ))
    checks.append(check(
        "target_collector_manual_only",
        "\n  workflow_dispatch:\n" in target_workflow
        and "\n  schedule:\n" not in target_workflow
        and "\n  repository_dispatch:\n" not in target_workflow
        and "permissions:\n  contents: read" in target_workflow,
        "Target collector template remains manual-only and read-only.",
        "Target collector trigger or permissions drifted.",
    ))

    target = config["repositories"]["acquisition"]
    repository = target["name"]
    repo_status, repo_value = github_get(f"/repos/{repository}")
    repo_ok = (
        repo_status == 200
        and isinstance(repo_value, dict)
        and int(repo_value.get("id", 0)) == int(target["id"])
        and repo_value.get("visibility") == "public"
        and repo_value.get("default_branch") == "main"
        and repo_value.get("archived") is False
    )
    checks.append(check(
        "target_repository_identity",
        repo_ok,
        "Target repository identity and public boundary match.",
        f"Target repository identity could not be verified: status={repo_status}.",
    ))

    pr_status, pr_value = github_get(f"/repos/{repository}/pulls/{target['pull_request']}")
    pr_ok = (
        pr_status == 200
        and isinstance(pr_value, dict)
        and pr_value.get("state") == "open"
        and pr_value.get("draft") is True
        and (pr_value.get("head") or {}).get("ref") == target["branch"]
        and (pr_value.get("base") or {}).get("ref") == "main"
    )
    checks.append(check(
        "target_pr_review_state",
        pr_ok,
        "Target PR 1 remains open, draft, and on the expected branches.",
        f"Target PR 1 is not in the expected review state: status={pr_status}.",
    ))

    readme_status, target_readme = public_file(repository, "README.md", target["branch"])
    readme_ok = readme_status == 200 and all(marker in target_readme for marker in (
        "Repository ID: `1312286476`",
        "exactly 50 retained paths",
        "PPI-R11-PUBLIC-ACQUISITION-003-R1",
        "Do not merge the bootstrap PR until",
    ))
    checks.append(check(
        "target_pr_hardened_readme",
        readme_ok,
        "Target PR branch contains the hardened README.",
        "Target PR branch still needs the current main-branch bootstrap rerun.",
    ))

    blocked = [item["name"] for item in checks if item["status"] != "pass"]
    return {
        "schema_version": "1.0.0",
        "scheduler_id": config["scheduler_id"],
        "phase": config["phase"],
        "active_task_id": config["active_task_id"],
        "status": "ready_for_target_pr_review" if not blocked else "blocked",
        "blocked_checks": blocked,
        "checks": checks,
        "next_manual_action": config["next_manual_action"],
        "authority": config["authority"],
        "run": {
            "repository": os.environ.get("GITHUB_REPOSITORY", ""),
            "repository_id": os.environ.get("GITHUB_REPOSITORY_ID", ""),
            "workflow": os.environ.get("GITHUB_WORKFLOW", ""),
            "run_id": os.environ.get("GITHUB_RUN_ID", ""),
            "attempt": os.environ.get("GITHUB_RUN_ATTEMPT", ""),
            "head_sha": os.environ.get("GITHUB_SHA", ""),
            "event": os.environ.get("GITHUB_EVENT_NAME", ""),
        },
    }


def write(report: dict[str, Any], output_root: Path) -> None:
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "readiness.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# PPI public migration scheduler",
        "",
        f"- Status: **{report['status']}**",
        f"- Active task: `{report['active_task_id']}`",
        "",
        "| Check | Status | Detail |",
        "|---|---|---|",
    ]
    for item in report["checks"]:
        detail = item["detail"].replace("|", "\\|").replace("\n", " ")
        lines.append(f"| `{item['name']}` | **{item['status']}** | {detail} |")
    lines.extend([
        "",
        "## Next manual action",
        "",
        report["next_manual_action"],
        "",
        "This scheduler is read-only and cannot collect data, dispatch private Actions, merge PRs, mutate the registry, or advance its task queue.",
        "",
    ])
    (output_root / "readiness.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--output-root", required=True)
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    report = build(config)
    write(report, Path(args.output_root))
    print(json.dumps({"status": report["status"], "blocked_checks": report["blocked_checks"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
