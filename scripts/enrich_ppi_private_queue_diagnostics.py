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
EXPECTED_INCLUDED_PRIVATE_MINUTES = 2000


class DiagnosticError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise DiagnosticError(message)


def api_get(path: str, *, token: str, version: str = "2022-11-28") -> tuple[int, Any]:
    request = Request(
        API_ROOT + path,
        method="GET",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": version,
            "User-Agent": "PPI private queue diagnostic",
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
        raise DiagnosticError(f"GitHub API network failure for {path}: {exc}") from exc
    value: Any = None
    if raw:
        try:
            value = json.loads(raw.decode("utf-8"))
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


def unique_append(items: list[str], value: str) -> None:
    if value not in items:
        items.append(value)


def minute_value(value: Any) -> float:
    if isinstance(value, bool):
        return 0.0
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def main() -> int:
    parser = argparse.ArgumentParser(description="Enrich a PPI autopilot report with private queue and Actions usage diagnostics")
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    token = os.environ.get("RAW_TOKEN", "").strip()
    require(token, "RAW_TOKEN is not configured")
    report = json.loads(args.report.read_text(encoding="utf-8"))
    require(isinstance(report, dict), "autopilot report must be an object")
    authority = report.get("authority")
    require(isinstance(authority, dict), "autopilot authority is missing")
    for key in ("registry_mutation", "production", "publication", "broker", "orders", "trading", "mmm_raw_data", "r12"):
        require(authority.get(key) is False, f"dangerous authority unexpectedly enabled: {key}")

    diagnostics: dict[str, Any] = {
        "schema_version": "1.1.0",
        "private_repository": PRIVATE_REPOSITORY,
        "private_repository_id": PRIVATE_REPOSITORY_ID,
        "configured_private_minute_ceiling": EXPECTED_INCLUDED_PRIVATE_MINUTES,
    }
    blocked = report.get("blocked_reasons")
    if not isinstance(blocked, list):
        blocked = []
        report["blocked_reasons"] = blocked

    status, repository = api_get(f"/repos/{PRIVATE_REPOSITORY}", token=token)
    require(status == 200 and isinstance(repository, dict), "private repository identity could not be verified")
    require(int(repository.get("id", 0)) == PRIVATE_REPOSITORY_ID, "private repository ID drift")
    require(repository.get("private") is True, "private repository must remain private")

    private_run = report.get("private_workflow")
    if isinstance(private_run, dict) and private_run.get("id"):
        run_id = int(private_run["id"])
        diagnostics["private_run_id"] = run_id
        diagnostics["private_run_status"] = private_run.get("status")
        diagnostics["private_run_conclusion"] = private_run.get("conclusion")
        status, jobs = api_get(f"/repos/{PRIVATE_REPOSITORY}/actions/runs/{run_id}/jobs?filter=latest&per_page=100", token=token)
        if status == 200 and isinstance(jobs, dict) and isinstance(jobs.get("jobs"), list):
            job_items = [item for item in jobs["jobs"] if isinstance(item, dict)]
            diagnostics["allocated_job_count"] = len(job_items)
            diagnostics["jobs"] = [
                {
                    "id": item.get("id"),
                    "name": item.get("name"),
                    "status": item.get("status"),
                    "conclusion": item.get("conclusion"),
                    "started_at": item.get("started_at"),
                    "completed_at": item.get("completed_at"),
                }
                for item in job_items[:5]
            ]
            created = parse_time(private_run.get("created_at"))
            queue_minutes = None
            if created is not None:
                queue_minutes = max(0.0, (datetime.now(timezone.utc) - created).total_seconds() / 60.0)
                diagnostics["queue_age_minutes"] = round(queue_minutes, 2)
            if private_run.get("status") in {"queued", "pending", "waiting"} and not job_items and (queue_minutes or 0) >= 5:
                unique_append(
                    blocked,
                    f"Private workflow run {run_id} remains queued with no allocated job after {round(queue_minutes or 0, 1)} minutes.",
                )
        else:
            diagnostics["jobs_probe"] = {"status": status, "available": False}

    login = str(report.get("token_login") or "")
    if login:
        old_status, old_value = api_get(f"/users/{login}/settings/billing/actions", token=token)
        diagnostics["legacy_actions_billing_probe_status"] = old_status
        if old_status == 200 and isinstance(old_value, dict):
            used = minute_value(old_value.get("total_minutes_used"))
            included = minute_value(old_value.get("included_minutes"))
            effective_ceiling = min(included, float(EXPECTED_INCLUDED_PRIVATE_MINUTES)) if included > 0 else None
            diagnostics["actions_minutes"] = {
                "total_minutes_used": used,
                "included_minutes": included,
                "effective_ceiling": effective_ceiling,
                "remaining_included_minutes": max(0.0, effective_ceiling - used) if effective_ceiling is not None else None,
            }
            if effective_ceiling is not None and used >= effective_ceiling:
                diagnostics["capacity_interpretation"] = "exact included-minute ceiling reached"
                unique_append(
                    blocked,
                    f"Private Actions included-minute ceiling is reached: {used:g} used of {effective_ceiling:g} allowed minutes.",
                )
            elif effective_ceiling is not None:
                diagnostics["capacity_interpretation"] = "exact included-minute capacity remains"
            else:
                diagnostics["capacity_interpretation"] = "legacy billing response did not expose an included-minute ceiling"
        elif old_status in {403, 404}:
            diagnostics["legacy_actions_billing_probe"] = "not_authorized_or_unavailable"

        now = datetime.now(timezone.utc)
        query = urlencode({"year": now.year, "month": now.month, "product": "Actions"})
        usage_status, usage_value = api_get(
            f"/users/{login}/settings/billing/usage/summary?{query}",
            token=token,
            version="2026-03-10",
        )
        diagnostics["actions_usage_summary_probe_status"] = usage_status
        if usage_status == 200 and isinstance(usage_value, dict):
            items = usage_value.get("usageItems")
            if isinstance(items, list):
                action_items = [
                    item
                    for item in items
                    if isinstance(item, dict)
                    and str(item.get("product", "")).lower() == "actions"
                    and str(item.get("unitType", "")).lower() == "minutes"
                ]
                gross = sum(minute_value(item.get("grossQuantity")) for item in action_items)
                discount = sum(minute_value(item.get("discountQuantity")) for item in action_items)
                net = sum(minute_value(item.get("netQuantity")) for item in action_items)
                diagnostics["actions_usage_summary"] = {
                    "gross_minutes": gross,
                    "discount_minutes": discount,
                    "net_minutes": net,
                    "item_count": len(action_items),
                }
                if "actions_minutes" not in diagnostics:
                    if gross > 0 and discount >= gross and net == 0:
                        diagnostics["capacity_interpretation"] = (
                            "gross Actions usage is fully discounted; it does not prove private included-minute exhaustion"
                        )
                    else:
                        diagnostics["capacity_interpretation"] = (
                            "usage-summary quantities do not expose exact private included-minute consumption"
                        )
        elif usage_status in {403, 404}:
            diagnostics["actions_usage_summary_probe"] = "not_authorized_or_unavailable"

    report["private_queue_diagnostics"] = diagnostics
    if blocked:
        report["status"] = "blocked"
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    markdown = args.report.with_name("autopilot.md")
    if markdown.exists():
        with markdown.open("a", encoding="utf-8") as handle:
            handle.write("\n## Private queue diagnostics\n\n")
            handle.write(f"- Private run: `{diagnostics.get('private_run_id', 'none')}`\n")
            handle.write(f"- Allocated jobs: `{diagnostics.get('allocated_job_count', 'unknown')}`\n")
            handle.write(f"- Queue age minutes: `{diagnostics.get('queue_age_minutes', 'unknown')}`\n")
            handle.write(f"- Capacity interpretation: `{diagnostics.get('capacity_interpretation', 'unresolved')}`\n")
            actions_minutes = diagnostics.get("actions_minutes")
            if isinstance(actions_minutes, dict):
                handle.write(
                    "- Included Actions minutes: "
                    f"`{actions_minutes.get('total_minutes_used')}` used / "
                    f"`{actions_minutes.get('effective_ceiling')}` ceiling\n"
                )
    print(json.dumps({"status": report.get("status"), "diagnostics": diagnostics}, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except DiagnosticError as exc:
        raise SystemExit(str(exc)) from exc
