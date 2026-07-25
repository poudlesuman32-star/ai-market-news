#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

API_ROOT = "https://api.github.com"
CANONICAL_PLAN = Path("docs/architecture/PPI_THREE_REPOSITORY_ARCHITECTURE_AND_MIGRATION_PLAN.md")
BOOTSTRAP_README = Path("bootstrap/ppi-data-acquisition/README.md")
BOOTSTRAP_WORKFLOW = Path(".github/workflows/bootstrap-ppi-data-acquisition.yml")
TARGET_WORKFLOW = Path("bootstrap/ppi-data-acquisition/.github/workflows/collect-r11-public-evidence.yml")


@dataclass(frozen=True)
class Check:
    name: str
    status: str
    detail: str


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def add_check(checks: list[Check], name: str, condition: bool, success: str, failure: str) -> None:
    checks.append(Check(name=name, status="pass" if condition else "blocked", detail=success if condition else failure))


def api_json(path: str) -> tuple[int, Any]:
    request = Request(
        API_ROOT + path,
        headers={
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "PPI public migration scheduler",
        },
        method="GET",
    )
    try:
        with urlopen(request, timeout=20) as response:
            raw = response.read()
            status = int(response.status)
    except HTTPError as exc:
        raw = exc.read()
        status = int(exc.code)
    except (URLError, TimeoutError, OSError) as exc:
        return 0, {"message": f"network_error: {exc}"}
    try:
        value: Any = json.loads(raw.decode("utf-8")) if raw else None
    except (UnicodeDecodeError, json.JSONDecodeError):
        value = {"message": raw.decode("utf-8", errors="replace")}
    return status, value


def fetch_public_text(repository: str, path: str, ref: str) -> tuple[int, str]:
    encoded_path = quote(path, safe="/")
    encoded_ref = quote(ref, safe="")
    status, value = api_json(f"/repos/{repository}/contents/{encoded_path}?ref={encoded_ref}")
    if status != 200 or not isinstance(value, dict):
        message = value.get("message") if isinstance(value, dict) else str(value)
        return status, f"GitHub API returned {status}: {message}"
    content = value.get("content")
    encoding = value.get("encoding")
    if not isinstance(content, str) or encoding != "base64":
        return status, "Unexpected GitHub content response"
    try:
        return status, base64.b64decode(content).decode("utf-8")
    except (ValueError, UnicodeDecodeError) as exc:
        return status, f"Could not decode target file: {exc}"


def build_report(config: dict[str, Any]) -> dict[str, Any]:
    require(config["schema_version"] == "1.0.0", "unexpected scheduler schema")
    require(config["enabled"] is True, "scheduler is disabled")
    require(config["phase"] == "gate-0-public-readiness", "only gate-0 is authorized in the initial scheduler")
    require(config["active_task_id"] == "T01", "only T01 is authorized in the initial scheduler")
    authority = config["authority"]
    for key in (
        "private_dispatch_authorized",
        "private_schedule_authorized",
        "automatic_merge_authorized",
        "provider_collection_authorized_by_this_scheduler",
        "registry_mutation_authorized",
        "production_authorized",
        "trading_authorized",
        "r12_authorized",
    ):
        require(authority[key] is False, f"scheduler unexpectedly authorizes {key}")
    require(authority["authorized_actions"] == [], "scheduler grants downstream authority")

    checks: list[Check] = []
    plan = CANONICAL_PLAN.read_text(encoding="utf-8")
    template_readme = BOOTSTRAP_README.read_text(encoding="utf-8")
    bootstrap_workflow = BOOTSTRAP_WORKFLOW.read_text(encoding="utf-8")
    target_workflow = TARGET_WORKFLOW.read_text(encoding="utf-8")

    add_check(
        checks,
        "canonical_plan_v1_2",
        "Decision document • Version 1.2" in plan and "Implementation status:** blocked" in plan,
        "Canonical Version 1.2 plan is present and remains fail-closed.",
        "Canonical plan is missing Version 1.2 or the blocked implementation status.",
    )
    add_check(
        checks,
        "stable_repository_ids",
        all(str(value) in plan for value in (1290414659, 1312286476, 1290626648)),
        "All three stable repository IDs are present.",
        "One or more stable repository IDs are missing from the canonical plan.",
    )
    add_check(
        checks,
        "hardened_bootstrap_readme",
        all(
            marker in template_readme
            for marker in (
                "Repository ID: `1312286476`",
                "exactly 50 retained paths",
                "PPI-R11-PUBLIC-ACQUISITION-003-R1",
                "public_storage_prohibited",
                "no external network",
                "Do not merge the bootstrap PR until",
            )
        ),
        "Bootstrap README contains the hardened trust, licensing, package, and merge boundaries.",
        "Bootstrap README is missing one or more hardened Version 1.2 markers.",
    )
    runtime_bootstrap = bootstrap_workflow.split("      - name: Validate source and generated target boundaries", 1)[0]
    add_check(
        checks,
        "bootstrap_manual_only",
        "\n  workflow_dispatch:\n" in bootstrap_workflow
        and "\n  schedule:\n" not in bootstrap_workflow
        and "\n  repository_dispatch:\n" not in bootstrap_workflow
        and "spoudel2010-ux/ppi-data-acquisition" in bootstrap_workflow
        and "secrets.RAW_TOKEN" in bootstrap_workflow,
        "Bootstrap remains manual-only, exact-target, and RAW_TOKEN-backed.",
        "Bootstrap trigger, target, or protected token binding drifted.",
    )
    add_check(
        checks,
        "bootstrap_no_private_dispatch",
        "musksuman3/ai-signal-engine" not in runtime_bootstrap
        and "repository_dispatch" not in runtime_bootstrap
        and "workflow_run" not in runtime_bootstrap,
        "Bootstrap runtime contains no private-repository dispatch path.",
        "Bootstrap runtime contains a private-dispatch or workflow fan-out marker.",
    )
    add_check(
        checks,
        "target_collector_manual_boundary",
        "\n  workflow_dispatch:\n" in target_workflow
        and "\n  schedule:\n" not in target_workflow
        and "\n  repository_dispatch:\n" not in target_workflow
        and "permissions:\n  contents: read" in target_workflow,
        "Target collector template remains manual-only and read-only.",
        "Target collector template trigger or permissions drifted.",
    )

    acquisition = config["repositories"]["acquisition"]
    target_repository = acquisition["name"]
    target_pr = int(acquisition["bootstrap_pr"])
    target_branch = acquisition["bootstrap_branch"]

    repo_status, repo_value = api_json(f"/repos/{target_repository}")
    repo_ok = (
        repo_status == 200
        and isinstance(repo_value, dict)
        and int(repo_value.get("id", 0)) == int(acquisition["id"])
        and repo_value.get("visibility") == "public"
        and repo_value.get("default_branch") == "main"
        and repo_value.get("archived") is False
    )
    add_check(
        checks,
        "target_repository_identity",
        repo_ok,
        "Target repository name, numeric ID, visibility, default branch, and archive state match.",
        f"Target repository identity could not be verified: status={repo_status}, response={repo_value!r}",
    )

    pr_status, pr_value = api_json(f"/repos/{target_repository}/pulls/{target_pr}")
    pr_ok = (
        pr_status == 200
        and isinstance(pr_value, dict)
        and pr_value.get("state") == "open"
        and pr_value.get("draft") is True
        and (pr_value.get("head") or {}).get("ref") == target_branch
        and (pr_value.get("base") or {}).get("ref") == "main"
    )
    add_check(
        checks,
        "target_bootstrap_pr_open_draft",
        pr_ok,
        "Target pull request 1 is open, draft, and uses the expected head and base branches.",
        f"Target pull request 1 is not in the expected review state: status={pr_status}, response={pr_value!r}",
    )

    readme_status, target_readme = fetch_public_text(target_repository, "README.md", target_branch)
    target_readme_hardened = readme_status == 200 and all(
        marker in target_readme
        for marker in (
            "Repository ID: `1312286476`",
            "exactly 50 retained paths",
            "PPI-R11-PUBLIC-ACQUISITION-003-R1",
            "Do not merge the bootstrap PR until",
        )
    )
    add_check(
        checks,
        "target_pr_hardened_readme",
        target_readme_hardened,
        "Target pull request branch contains the hardened README.",
        "Target pull request branch does not yet contain the hardened README; run the current main-branch bootstrap once.",
    )

    blocked = [check.name for check in checks if check.status != "pass"]
    status = "ready_for_target_pr_review" if not blocked else "blocked"
    return {
        "schema_version": "1.0.0",
        "scheduler_id": config["scheduler_id"],
        "phase": config["phase"],
        "active_task": config["active_task"],
        "generated_by": {
            "repository": os.environ.get("GITHUB_REPOSITORY", ""),
            "repository_id": os.environ.get("GITHUB_REPOSITORY_ID", ""),
            "workflow": os.environ.get("GITHUB_WORKFLOW", ""),
            "run_id": os.environ.get("GITHUB_RUN_ID", ""),
            "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT", ""),
            "head_sha": os.environ.get("GITHUB_SHA", ""),
            "event": os.environ.get("GITHUB_EVENT_NAME", ""),
        },
        "status": status,
        "blocked_checks": blocked,
        "checks": [asdict(check) for check in checks],
        "authority": authority,
        "next_manual_action": config["active_task"]["next_manual_action"],
    }


def write_report(report: dict[str, Any], output_root: Path) -> None:
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "readiness.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# PPI public migration scheduler",
        "",
        f"- Status: **{report['status']}**",
        f"- Phase: `{report['phase']}`",
        f"- Active task: `{report['active_task']['id']}` — {report['active_task']['name']}",
        "",
        "## Checks",
        "",
        "| Check | Status | Detail |",
        "|---|---|---|",
    ]
    for check in report["checks"]:
        detail = str(check["detail"]).replace("|", "\\|").replace("\n", " ")
        lines.append(f"| `{check['name']}` | **{check['status']}** | {detail} |")
    lines.extend(
        [
            "",
            "## Next manual action",
            "",
            report["next_manual_action"],
            "",
            "This scheduler is read-only. It does not collect provider data, dispatch the private repository, merge pull requests, mutate the registry, or grant downstream authority.",
            "",
        ]
    )
    (output_root / "readiness.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the read-only PPI public migration readiness report")
    parser.add_argument("--config", required=True)
    parser.add_argument("--output-root", required=True)
    args = parser.parse_args()

    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    report = build_report(config)
    write_report(report, Path(args.output_root))
    print(json.dumps({"status": report["status"], "blocked_checks": report["blocked_checks"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
