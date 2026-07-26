#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from typing import Any

import ppi_migration_autopilot_v3 as v3

PRIVATE_RUN_TITLE = re.compile(r"^Final private analysis for public run ([0-9]+)$")
PRIVATE_RUN_TITLE_SEARCH = re.compile(r"Final private analysis for public run ([0-9]+)")
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
    exact = PRIVATE_RUN_TITLE.fullmatch(title)
    if exact:
        return exact.group(1)
    serialized = json.dumps(run, sort_keys=True, separators=(",", ":"))
    fallback = PRIVATE_RUN_TITLE_SEARCH.search(serialized)
    return fallback.group(1) if fallback else None


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


def exact_private_minute_usage(token: str, login: str) -> tuple[float | None, float | None, str]:
    """Return included-minute usage only when GitHub exposes the exact legacy meter.

    The newer usage-summary endpoint reports gross, discounted, and net quantities.
    Public-repository minutes can appear in gross usage and be fully discounted, so
    gross usage alone is never used as a private-capacity gate.
    """
    try:
        raw = v3.v2.base.run_command(
            ["gh", "api", "--method", "GET", f"/users/{login}/settings/billing/actions"],
            env={"GH_TOKEN": token},
        )
        value = json.loads(raw or "{}")
    except Exception as exc:
        return None, None, f"exact included-minute probe unavailable: {exc}"
    if not isinstance(value, dict):
        return None, None, "exact included-minute probe returned an unexpected shape"
    try:
        used = float(value.get("total_minutes_used"))
        included = float(value.get("included_minutes"))
    except (TypeError, ValueError):
        return None, None, "exact included-minute probe omitted numeric usage fields"
    return used, included, f"exact private Actions usage is {used:g} of {included:g} included minutes"


def run_sort_key(run: dict[str, Any]) -> tuple[int, datetime]:
    status = str(run.get("status") or "")
    priority = 0 if status == "in_progress" else 1
    created = parse_time(run.get("created_at")) or datetime.max.replace(tzinfo=timezone.utc)
    return priority, created


def dispatch_exact_private_run(token: str, public_run: dict[str, Any]) -> tuple[bool, str]:
    public_run_id = str(public_run.get("id") or "")
    public_head_sha = str(public_run.get("head_sha") or "").lower()
    v3.v2.base.require(public_run_id.isdigit(), "public run ID is invalid")
    v3.v2.base.require(
        len(public_head_sha) == 40 and all(char in "0123456789abcdef" for char in public_head_sha),
        "public head SHA is invalid",
    )

    runs = v3.v2.base.list_workflow_runs(v3.v2.base.PRIVATE_REPOSITORY, v3.v2.base.PRIVATE_WORKFLOW, token)
    matching = [run for run in runs if public_run_id_from_private_run(run) == public_run_id]
    unknown_active = [
        run
        for run in runs
        if str(run.get("status") or "") in ACTIVE_STATUSES
        and public_run_id_from_private_run(run) is None
    ]
    if unknown_active:
        ids = [str(run.get("id")) for run in unknown_active]
        return False, f"private dispatch blocked by active workflow runs with unrecognized titles: {', '.join(ids)}"

    active = [run for run in matching if str(run.get("status") or "") in ACTIVE_STATUSES]
    if active:
        ordered = sorted(active, key=run_sort_key)
        keeper = ordered[0]
        in_progress = [run for run in ordered if str(run.get("status") or "") == "in_progress"]
        if len(in_progress) > 1:
            ids = [str(run.get("id")) for run in in_progress]
            return False, f"multiple private analyses are already in progress for public run {public_run_id}: {', '.join(ids)}"

        cancelled: list[int] = []
        unresolved: list[int] = []
        for duplicate in ordered[1:]:
            duplicate_id = int(duplicate.get("id") or 0)
            if duplicate_id <= 0 or str(duplicate.get("status") or "") not in QUEUED_STATUSES:
                continue
            if cancel_private_run(token, duplicate_id):
                cancelled.append(duplicate_id)
            else:
                unresolved.append(duplicate_id)

        detail = (
            f"private analysis already exists for public run {public_run_id}: "
            f"run {keeper.get('id')} is {keeper.get('status')} with conclusion {keeper.get('conclusion')}"
        )
        if cancelled:
            detail += f"; cancelled redundant queued runs {cancelled}"
        if unresolved:
            detail += f"; redundant queued runs could not be cancelled {unresolved}"
        return False, detail

    successful = [run for run in matching if run.get("status") == "completed" and run.get("conclusion") == "success"]
    if successful:
        run = sorted(
            successful,
            key=lambda item: parse_time(item.get("created_at")) or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )[0]
        return False, f"private analysis run {run.get('id')} already succeeded for public run {public_run_id}"

    unsuccessful = [
        run
        for run in matching
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
            return False, (
                f"private analysis run {newest_id} already executed and concluded {newest.get('conclusion')}; "
                "automatic retry is disabled"
            )
        if same_month:
            return False, (
                f"zero-job private run {newest_id} concluded {newest.get('conclusion')} in the current billing month; "
                "retry waits for the next month"
            )

    used, included, usage_detail = exact_private_minute_usage(token, v3.v2.base.authenticated_login(token))
    if used is not None and included is not None and included > 0:
        effective_ceiling = min(included, PRIVATE_MINUTE_CEILING)
        if used >= effective_ceiling:
            return False, f"private dispatch blocked at the {effective_ceiling:g}-minute ceiling; {usage_detail}"

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
            suffix = "" if used is not None else f"; {usage_detail}"
            return True, (
                f"dispatched private analysis for public run {public_run_id}; "
                f"private workflow run {visible.get('id')} is {visible.get('status')} "
                f"with conclusion {visible.get('conclusion')}{suffix}"
            )
        if attempt < 6:
            time.sleep(5)
    suffix = "" if used is not None else f"; {usage_detail}"
    return True, f"dispatched private analysis for public run {public_run_id}; run not visible after 30 seconds{suffix}"


def main() -> int:
    v3.dispatch_private_with_visibility = dispatch_exact_private_run
    return v3.main()


if __name__ == "__main__":
    raise SystemExit(main())
