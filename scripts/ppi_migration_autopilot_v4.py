#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode

import ppi_migration_autopilot_v3 as v3

PRIVATE_RUN_TITLE = re.compile(r"^Final private analysis for public run ([0-9]+)$")
ACTIVE_STATUSES = {"queued", "pending", "waiting", "requested", "in_progress"}
QUEUED_STATUSES = {"queued", "pending", "waiting", "requested"}
PRIVATE_MINUTE_CEILING = 2000.0


def parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def public_run_id_from_private_run(run: dict[str, Any]) -> str | None:
    title = str(run.get("display_title") or "")
    match = PRIVATE_RUN_TITLE.fullmatch(title)
    return match.group(1) if match else None


def jobs_for_run(token: str, run_id: int) -> list[dict[str, Any]] | None:
    status, value = v3.v2.base.api(
        "GET",
        f"/repos/{v3.v2.base.PRIVATE_REPOSITORY}/actions/runs/{run_id}/jobs?filter=latest&per_page=100",
        token=token,
        allowed_statuses=(200, 404),
    )
    if status == 404:
        return None
    v3.v2.base.require(isinstance(value, dict) and isinstance(value.get("jobs"), list), "unexpected private jobs response")
    return [item for item in value["jobs"] if isinstance(item, dict)]


def cancel_private_run(token: str, run_id: int) -> bool:
    status, _ = v3.v2.base.api(
        "POST",
        f"/repos/{v3.v2.base.PRIVATE_REPOSITORY}/actions/runs/{run_id}/cancel",
        token=token,
        allowed_statuses=(202, 409),
    )
    return status == 202


def actions_gross_minutes(token: str, login: str) -> tuple[float | None, str]:
    now = datetime.now(timezone.utc)
    query = urlencode({"year": now.year, "month": now.month, "product": "Actions"})
    try:
        raw = v3.v2.base.run_command(
            [
                "gh",
                "api",
                "--method",
                "GET",
                "-H",
                "X-GitHub-Api-Version: 2026-03-10",
                f"/users/{login}/settings/billing/usage/summary?{query}",
            ],
            env={"GH_TOKEN": token},
        )
        value = json.loads(raw or "{}")
    except Exception as exc:
        return None, f"Actions usage probe unavailable: {exc}"
    if not isinstance(value, dict) or not isinstance(value.get("usageItems"), list):
        return None, "Actions usage probe returned an unexpected shape"
    gross = 0.0
    count = 0
    for item in value["usageItems"]:
        if not isinstance(item, dict):
            continue
        if str(item.get("product", "")).lower() != "actions":
            continue
        if str(item.get("unitType", "")).lower() != "minutes":
            continue
        try:
            gross += float(item.get("grossQuantity") or 0)
            count += 1
        except (TypeError, ValueError):
            continue
    if count == 0:
        return 0.0, "Actions usage summary contains no minute items"
    return gross, f"Actions gross minutes for {now.year}-{now.month:02d}: {gross:g}"


def run_sort_key(run: dict[str, Any]) -> tuple[int, datetime]:
    status = str(run.get("status") or "")
    priority = 0 if status == "in_progress" else 1
    created = parse_time(run.get("created_at")) or datetime.max.replace(tzinfo=timezone.utc)
    return priority, created


def dispatch_exact_private_run(token: str, public_run: dict[str, Any]) -> tuple[bool, str]:
    public_run_id = str(public_run.get("id") or "")
    public_head_sha = str(public_run.get("head_sha") or "").lower()
    v3.v2.base.require(public_run_id.isdigit(), "public run ID is invalid")
    v3.v2.base.require(len(public_head_sha) == 40 and all(char in "0123456789abcdef" for char in public_head_sha), "public head SHA is invalid")

    runs = v3.v2.base.list_workflow_runs(v3.v2.base.PRIVATE_REPOSITORY, v3.v2.base.PRIVATE_WORKFLOW, token)
    matching = [run for run in runs if public_run_id_from_private_run(run) == public_run_id]
    unknown_active = [
        run for run in runs
        if str(run.get("status") or "") in ACTIVE_STATUSES
        and public_run_id_from_private_run(run) is None
    ]
    if unknown_active:
        ids = [str(run.get("id")) for run in unknown_active]
        return False, f"private dispatch blocked by active workflow runs with unrecognized titles: {', '.join(ids)}"

    active = [run for run in matching if str(run.get("status") or "") in ACTIVE_STATUSES]
    cancelled: list[int] = []
    if active:
        ordered = sorted(active, key=run_sort_key)
        keeper = ordered[0]
        in_progress = [run for run in ordered if str(run.get("status") or "") == "in_progress"]
        if len(in_progress) > 1:
            ids = [str(run.get("id")) for run in in_progress]
            return False, f"multiple private analyses are already in progress for public run {public_run_id}: {', '.join(ids)}"
        for duplicate in ordered[1:]:
            duplicate_id = int(duplicate.get("id") or 0)
            if duplicate_id > 0 and str(duplicate.get("status") or "") in QUEUED_STATUSES:
                if cancel_private_run(token, duplicate_id):
                    cancelled.append(duplicate_id)
        detail = (
            f"private analysis already exists for public run {public_run_id}: "
            f"run {keeper.get('id')} is {keeper.get('status')} with conclusion {keeper.get('conclusion')}"
        )
        if cancelled:
            detail += f"; cancelled redundant queued runs {cancelled}"
        return False, detail

    successful = [run for run in matching if run.get("status") == "completed" and run.get("conclusion") == "success"]
    if successful:
        run = sorted(successful, key=lambda item: parse_time(item.get("created_at")) or datetime.min.replace(tzinfo=timezone.utc), reverse=True)[0]
        return False, f"private analysis run {run.get('id')} already succeeded for public run {public_run_id}"

    gross, usage_detail = actions_gross_minutes(token, v3.v2.base.authenticated_login(token))
    if gross is None:
        return False, f"private dispatch failed closed because {usage_detail}"
    if gross >= PRIVATE_MINUTE_CEILING:
        return False, f"private dispatch blocked at the {PRIVATE_MINUTE_CEILING:g}-minute ceiling; {usage_detail}"

    unsuccessful = [
        run for run in matching
        if run.get("status") == "completed"
        and run.get("conclusion") in {"failure", "cancelled", "timed_out", "startup_failure"}
    ]
    if unsuccessful:
        newest = sorted(
            unsuccessful,
            key=lambda item: parse_time(item.get("created_at")) or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )[0]
        newest_id = int(newest.get("id") or 0)
        jobs = jobs_for_run(token, newest_id) if newest_id > 0 else None
        created = parse_time(newest.get("created_at"))
        now = datetime.now(timezone.utc)
        same_month = bool(created and created.year == now.year and created.month == now.month)
        if jobs:
            return False, f"private analysis run {newest_id} already executed and concluded {newest.get('conclusion')}; automatic retry is disabled"
        if same_month:
            return False, f"zero-job private run {newest_id} concluded {newest.get('conclusion')} in the current billing month; retry waits for the next month"

    v3.v2.base.api(
        "POST",
        f"/repos/{v3.v2.base.PRIVATE_REPOSITORY}/actions/workflows/{v3.v2.base.PRIVATE_WORKFLOW}/dispatches",
        token=token,
        payload={
            "ref": "main",
            "inputs": {
                "public_run_id": public_run_id,
                "public_head_sha": public_head_sha,
            },
        },
        allowed_statuses=(204,),
    )
    for attempt in range(7):
        visible_runs = v3.v2.base.list_workflow_runs(v3.v2.base.PRIVATE_REPOSITORY, v3.v2.base.PRIVATE_WORKFLOW, token)
        visible = next((run for run in visible_runs if public_run_id_from_private_run(run) == public_run_id), None)
        if visible is not None:
            return True, (
                f"dispatched private analysis for public run {public_run_id}; "
                f"private workflow run {visible.get('id')} is {visible.get('status')} "
                f"with conclusion {visible.get('conclusion')}"
            )
        if attempt < 6:
            time.sleep(5)
    return True, f"dispatched private analysis for public run {public_run_id}; run not visible after 30 seconds"


def main() -> int:
    v3.dispatch_private_with_visibility = dispatch_exact_private_run
    return v3.main()


if __name__ == "__main__":
    raise SystemExit(main())
