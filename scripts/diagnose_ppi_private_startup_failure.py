#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API_ROOT = "https://api.github.com"
PRIVATE_REPOSITORY = "musksuman3/ai-signal-engine"
PRIVATE_REPOSITORY_ID = 1290626648
PRIVATE_WORKFLOW = "ppi-r11-private-final-analysis.yml"
FAILED_RUN_ID = 30188784601
EXPECTED_PRIVATE_HEAD_SHA = "49cbb0ce6aaa9bdb2e63dc54ac443a2b5cf6b312"
BILLING_YEAR = 2026
BILLING_MONTH = 7


class StartupDiagnosticError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise StartupDiagnosticError(message)


def api_get(path: str, *, token: str, version: str = "2022-11-28") -> tuple[int, Any]:
    request = Request(
        API_ROOT + path,
        method="GET",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": version,
            "User-Agent": "PPI exact private startup diagnostic",
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
        raise StartupDiagnosticError(f"GitHub API network failure for {path}: {exc}") from exc
    try:
        value: Any = json.loads(raw.decode("utf-8")) if raw else None
    except (UnicodeDecodeError, json.JSONDecodeError):
        value = raw.decode("utf-8", errors="replace")
    return status, value


def parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def numeric(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def unique_append(items: list[str], value: str) -> None:
    if value not in items:
        items.append(value)


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnose one private workflow startup failure without rerunning it")
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    token = os.environ.get("RAW_TOKEN", "").strip()
    require(token, "RAW_TOKEN is not configured")
    report = json.loads(args.report.read_text(encoding="utf-8"))
    require(isinstance(report, dict), "autopilot report must be an object")
    blocked = report.get("blocked_reasons")
    if not isinstance(blocked, list):
        blocked = []
        report["blocked_reasons"] = blocked

    status, repository = api_get(f"/repos/{PRIVATE_REPOSITORY}", token=token)
    require(status == 200 and isinstance(repository, dict), "private repository identity could not be verified")
    require(int(repository.get("id", 0)) == PRIVATE_REPOSITORY_ID, "private repository ID drift")
    require(repository.get("private") is True and repository.get("archived") is False, "private repository boundary mismatch")

    status, run = api_get(f"/repos/{PRIVATE_REPOSITORY}/actions/runs/{FAILED_RUN_ID}", token=token)
    require(status == 200 and isinstance(run, dict), "failed private run could not be read")
    require(str(run.get("head_sha") or "").lower() == EXPECTED_PRIVATE_HEAD_SHA, "failed run private SHA mismatch")
    require(run.get("status") == "completed" and run.get("conclusion") == "failure", "target run is not the expected terminal failure")

    diagnostic: dict[str, Any] = {
        "schema_version": "1.0.0",
        "run": {
            "id": run.get("id"),
            "status": run.get("status"),
            "conclusion": run.get("conclusion"),
            "event": run.get("event"),
            "head_branch": run.get("head_branch"),
            "head_sha": run.get("head_sha"),
            "path": run.get("path"),
            "run_started_at": run.get("run_started_at"),
            "created_at": run.get("created_at"),
            "updated_at": run.get("updated_at"),
            "html_url": run.get("html_url"),
        },
    }

    status, workflow = api_get(f"/repos/{PRIVATE_REPOSITORY}/actions/workflows/{PRIVATE_WORKFLOW}", token=token)
    diagnostic["workflow_probe_status"] = status
    if status == 200 and isinstance(workflow, dict):
        diagnostic["workflow"] = {
            "id": workflow.get("id"),
            "name": workflow.get("name"),
            "path": workflow.get("path"),
            "state": workflow.get("state"),
            "created_at": workflow.get("created_at"),
            "updated_at": workflow.get("updated_at"),
        }

    status, permissions = api_get(f"/repos/{PRIVATE_REPOSITORY}/actions/permissions", token=token)
    diagnostic["permissions_probe_status"] = status
    if status == 200 and isinstance(permissions, dict):
        diagnostic["permissions"] = {
            "enabled": permissions.get("enabled"),
            "allowed_actions": permissions.get("allowed_actions"),
            "sha_pinning_required": permissions.get("sha_pinning_required"),
        }

    status, selected = api_get(f"/repos/{PRIVATE_REPOSITORY}/actions/permissions/selected-actions", token=token)
    diagnostic["selected_actions_probe_status"] = status
    if status == 200 and isinstance(selected, dict):
        diagnostic["selected_actions"] = {
            "github_owned_allowed": selected.get("github_owned_allowed"),
            "verified_allowed": selected.get("verified_allowed"),
            "patterns_allowed": selected.get("patterns_allowed") or [],
        }

    status, jobs = api_get(f"/repos/{PRIVATE_REPOSITORY}/actions/runs/{FAILED_RUN_ID}/jobs?filter=latest&per_page=100", token=token)
    require(status == 200 and isinstance(jobs, dict) and isinstance(jobs.get("jobs"), list), "failed run jobs could not be read")
    job_items = [item for item in jobs["jobs"] if isinstance(item, dict)]
    diagnostic["job_count"] = len(job_items)
    diagnostic_jobs: list[dict[str, Any]] = []
    for item in job_items:
        job_id = int(item.get("id") or 0)
        detail_status, detail = api_get(f"/repos/{PRIVATE_REPOSITORY}/actions/jobs/{job_id}", token=token) if job_id > 0 else (0, None)
        source = detail if detail_status == 200 and isinstance(detail, dict) else item
        steps = source.get("steps") if isinstance(source.get("steps"), list) else []
        started = parse_time(source.get("started_at"))
        completed = parse_time(source.get("completed_at"))
        duration = None
        if started is not None and completed is not None:
            duration = round(max(0.0, (completed - started).total_seconds()), 3)
        diagnostic_jobs.append({
            "id": source.get("id"),
            "name": source.get("name"),
            "status": source.get("status"),
            "conclusion": source.get("conclusion"),
            "started_at": source.get("started_at"),
            "completed_at": source.get("completed_at"),
            "duration_seconds": duration,
            "runner_id": source.get("runner_id"),
            "runner_name": source.get("runner_name"),
            "runner_group_id": source.get("runner_group_id"),
            "runner_group_name": source.get("runner_group_name"),
            "labels": source.get("labels") or [],
            "step_count": len(steps),
            "steps": [
                {
                    "name": step.get("name"),
                    "status": step.get("status"),
                    "conclusion": step.get("conclusion"),
                    "number": step.get("number"),
                    "started_at": step.get("started_at"),
                    "completed_at": step.get("completed_at"),
                }
                for step in steps[:20]
                if isinstance(step, dict)
            ],
            "detail_probe_status": detail_status,
        })
    diagnostic["jobs"] = diagnostic_jobs

    no_steps = bool(diagnostic_jobs) and all(int(job.get("step_count") or 0) == 0 for job in diagnostic_jobs)
    no_runner = bool(diagnostic_jobs) and all(not job.get("runner_id") and not job.get("runner_name") for job in diagnostic_jobs)
    if no_steps and no_runner:
        diagnostic["classification"] = "pre_step_failure_without_runner_assignment"
        unique_append(blocked, f"Private recovery run {FAILED_RUN_ID} failed before any step and without a runner assignment.")
    elif no_steps:
        diagnostic["classification"] = "pre_step_failure_after_runner_assignment"
        unique_append(blocked, f"Private recovery run {FAILED_RUN_ID} failed before any workflow step.")
    else:
        diagnostic["classification"] = "workflow_step_failure"

    query = urlencode({"year": BILLING_YEAR, "month": BILLING_MONTH})
    status, usage = api_get(
        f"/users/musksuman3/settings/billing/usage?{query}",
        token=token,
        version="2026-03-10",
    )
    diagnostic["usage_report_probe_status"] = status
    if status == 200 and isinstance(usage, dict) and isinstance(usage.get("usageItems"), list):
        private_items = [
            item
            for item in usage["usageItems"]
            if isinstance(item, dict)
            and str(item.get("product") or "").lower() == "actions"
            and str(item.get("repositoryName") or "").lower() == PRIVATE_REPOSITORY.lower()
        ]
        diagnostic["private_repository_billing_usage"] = {
            "item_count": len(private_items),
            "quantity": sum(numeric(item.get("quantity")) for item in private_items),
            "gross_amount": sum(numeric(item.get("grossAmount")) for item in private_items),
            "discount_amount": sum(numeric(item.get("discountAmount")) for item in private_items),
            "net_amount": sum(numeric(item.get("netAmount")) for item in private_items),
            "skus": sorted({str(item.get("sku") or "") for item in private_items}),
        }

    diagnostic["generated_at_utc"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    report["private_startup_failure"] = diagnostic
    if blocked:
        report["status"] = "blocked"
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": report.get("status"), "private_startup_failure": diagnostic}, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except StartupDiagnosticError as exc:
        raise SystemExit(str(exc)) from exc
