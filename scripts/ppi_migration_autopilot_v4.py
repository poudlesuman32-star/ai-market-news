#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any

import ppi_migration_autopilot_v3 as v3

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


def is_authorized_private_workflow_run(run: dict[str, Any]) -> bool:
    return (
        str(run.get("event") or "") == "workflow_dispatch"
        and str(run.get("head_branch") or "") == "main"
    )


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


def cancel_private_run(token: str, run_id: int) -> tuple[bool, str]:
    errors: list[str] = []
    try:
        status, _ = v3.v2.base.api(
            "POST",
            f"/repos/{v3.v2.base.PRIVATE_REPOSITORY}/actions/runs/{run_id}/cancel",
            token=token,
            allowed_statuses=(202, 409),
        )
        if status == 202:
            return True, "cancelled through GitHub Actions REST"
        errors.append("GitHub Actions REST returned 409")
    except Exception as exc:
        errors.append(f"GitHub Actions REST failed: {exc}")

    try:
        v3.v2.base.run_command(
            ["gh", "run", "cancel", str(run_id), "--repo", v3.v2.base.PRIVATE_REPOSITORY],
            env={"GH_TOKEN": token},
        )
        return True, "cancelled through gh run cancel"
    except Exception as exc:
        errors.append(f"gh run cancel failed: {exc}")
    return False, " | ".join(errors)


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


def within_authorization_window(run: dict[str, Any], public_run: dict[str, Any]) -> bool:
    run_created = parse_time(run.get("created_at"))
    public_completed = parse_time(public_run.get("updated_at")) or parse_time(public_run.get("created_at"))
    return bool(run_created and public_completed and run_created >= public_completed)


def dispatch_exact_private_run(token: str, public_run: dict[str, Any]) -> tuple[bool, str]:
    public_run_id = str(public_run.get("id") or "")
    public_head_sha = str(public_run.get("head_sha") or "").lower()
    v3.v2.base.require(public_run_id.isdigit(), "public run ID is invalid")
    v3.v2.base.require(
        len(public_head_sha) == 40 and all(char in "0123456789abcdef" for char in public_head_sha),
        "public head SHA is invalid",
    )
    v3.v2.base.require(
        parse_time(public_run.get("updated_at")) is not None or parse_time(public_run.get("created_at")) is not None,
        "public run authorization time is missing",
    )

    runs = v3.v2.base.list_workflow_runs(v3.v2.base.PRIVATE_REPOSITORY, v3.v2.base.PRIVATE_WORKFLOW, token)
    active = [run for run in runs if str(run.get("status") or "") in ACTIVE_STATUSES]
    invalid_active = [run for run in active if not is_authorized_private_workflow_run(run)]
    if invalid_active:
        ids = [str(run.get("id")) for run in invalid_active]
        return False, f"private singleton blocked by active runs outside workflow_dispatch/main: {', '.join(ids)}"

    authorized_active = [run for run in active if is_authorized_private_workflow_run(run)]
    if authorized_active:
        ordered = sorted(authorized_active, key=run_sort_key)
        keeper = ordered[0]
        in_progress = [run for run in ordered if str(run.get("status") or "") == "in_progress"]
        if len(in_progress) > 1:
            ids = [str(run.get("id")) for run in in_progress]
            return False, f"multiple private final analyses are already in progress: {', '.join(ids)}"

        cancelled: list[int] = []
        unresolved: list[str] = []
        for duplicate in ordered[1:]:
            duplicate_id = int(duplicate.get("id") or 0)
            if duplicate_id <= 0 or str(duplicate.get("status") or "") not in QUEUED_STATUSES:
                continue
            was_cancelled, cancellation_detail = cancel_private_run(token, duplicate_id)
            if was_cancelled:
                cancelled.append(duplicate_id)
            else:
                unresolved.append(f"{duplicate_id} ({cancellation_detail})")

        detail = (
            f"private final-analysis singleton retained for public run {public_run_id}: "
            f"run {keeper.get('id')} is {keeper.get('status')} with conclusion {keeper.get('conclusion')}"
        )
        if cancelled:
            detail += f"; cancelled redundant queued runs {cancelled}"
        if unresolved:
            detail += f"; redundant queued runs could not be cancelled: {'; '.join(unresolved)}"
        return False, detail

    authorized_window_runs = [
        run
        for run in runs
        if is_authorized_private_workflow_run(run) and within_authorization_window(run, public_run)
    ]
    successful = [
        run
        for run in authorized_window_runs
        if run.get("status") == "completed" and run.get("conclusion") == "success"
    ]
    if successful:
        run = sorted(
            successful,
            key=lambda item: parse_time(item.get("created_at")) or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )[0]
        return False, f"private final-analysis run {run.get('id')} already succeeded in the current public authorization window"

    unsuccessful = [
        run
        for run in authorized_window_runs
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
                f"private final-analysis run {newest_id} already executed and concluded {newest.get('conclusion')}; "
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
        visible = next(
            (
                run
                for run in visible_runs
                if is_authorized_private_workflow_run(run)
                and str(run.get("status") or "") in ACTIVE_STATUSES
                and within_authorization_window(run, public_run)
            ),
            None,
        )
        if visible is not None:
            suffix = "" if used is not None else f"; {usage_detail}"
            return True, (
                f"dispatched private final-analysis singleton for public run {public_run_id}; "
                f"run {visible.get('id')} is {visible.get('status')} with conclusion {visible.get('conclusion')}{suffix}"
            )
        if attempt < 6:
            time.sleep(5)
    suffix = "" if used is not None else f"; {usage_detail}"
    return True, f"dispatched private final-analysis singleton for public run {public_run_id}; run not visible after 30 seconds{suffix}"


def main() -> int:
    v3.dispatch_private_with_visibility = dispatch_exact_private_run
    return v3.main()


if __name__ == "__main__":
    raise SystemExit(main())
