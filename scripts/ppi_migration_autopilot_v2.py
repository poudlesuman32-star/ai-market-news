#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from datetime import timedelta
from pathlib import Path
from typing import Any
from urllib.parse import quote

import ppi_migration_autopilot as base


def list_target_secret_names(token: str) -> tuple[set[str] | None, str | None]:
    try:
        raw = base.run_command(
            ["gh", "secret", "list", "--repo", base.TARGET_REPOSITORY, "--json", "name"],
            env={"GH_TOKEN": token},
        )
        value = json.loads(raw or "[]")
        base.require(isinstance(value, list), "target secret list is not an array")
        return {
            str(item.get("name", ""))
            for item in value
            if isinstance(item, dict) and isinstance(item.get("name"), str)
        }, None
    except Exception as exc:
        return None, str(exc)


def run_summary(run: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(run, dict):
        return None
    return {
        "id": run.get("id"),
        "status": run.get("status"),
        "conclusion": run.get("conclusion"),
        "event": run.get("event"),
        "head_sha": run.get("head_sha"),
        "created_at": run.get("created_at"),
        "updated_at": run.get("updated_at"),
        "html_url": run.get("html_url"),
    }


def target_main_sha(token: str) -> str:
    _, value = base.api("GET", f"/repos/{base.TARGET_REPOSITORY}/git/ref/heads/main", token=token)
    base.require(isinstance(value, dict), "unexpected target main ref response")
    sha = (value.get("object") or {}).get("sha")
    base.require(isinstance(sha, str) and len(sha) == 40, "target main SHA is invalid")
    return sha


def current_target_pr(token: str) -> dict[str, Any] | None:
    owner = base.TARGET_REPOSITORY.split("/", 1)[0]
    _, value = base.api(
        "GET",
        f"/repos/{base.TARGET_REPOSITORY}/pulls?state=open&head={quote(owner + ':' + base.TARGET_BRANCH, safe=':')}&base=main",
        token=token,
    )
    base.require(isinstance(value, list), "unexpected target pull request response")
    base.require(len(value) <= 1, "multiple open acquisition update pull requests exist")
    return value[0] if value else None


def target_gate(token: str, ref: str) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    required_paths = (
        "README.md",
        ".github/workflows/collect-r11-public-evidence.yml",
        "config/r11_batch_003.json",
        "config/provider_licensing_dispositions.json",
        "contracts/PPI-R11-PUBLIC-ACQUISITION-003-R1.json",
        "contracts/PPI-PUBLIC-COLLECTOR-003-R1.json",
        "src/collect_raw_provider_evidence.py",
        "src/fetch_yfinance_expectations.py",
        "src/publish_private_handoff.py",
        "tests/test_public_boundary.py",
    )
    values: dict[str, str] = {}
    for path in required_paths:
        try:
            values[path] = base.fetch_text(base.TARGET_REPOSITORY, path, ref, token)
        except Exception:
            reasons.append(f"target {ref} is missing {path}")
    workflow = values.get(".github/workflows/collect-r11-public-evidence.yml", "")
    scope = values.get("config/r11_batch_003.json", "")
    licensing = values.get("config/provider_licensing_dispositions.json", "")
    collector = values.get("src/collect_raw_provider_evidence.py", "")
    helper = values.get("src/fetch_yfinance_expectations.py", "")
    for marker in (
        "PRIVATE_RELEASE_HANDOFF_ENABLED: true",
        "ppi-r11-public-success-",
        "ppi-r11-public-failure-",
        "persist-credentials: false",
        "'yfinance==1.5.1'",
        "src/fetch_yfinance_expectations.py",
    ):
        if marker not in workflow:
            reasons.append(f"collector workflow missing marker: {marker}")
    if "actions/checkout@v" in workflow or "actions/upload-artifact@v" in workflow:
        reasons.append("collector workflow contains mutable action tags")
    for marker in (
        '"expectation_provider": "yahoo_finance_via_yfinance"',
        '"expected_alpha_vantage_request_count": 12',
        '"expected_bundle_count": 48',
        '"expected_path_count": 50',
    ):
        if marker not in scope:
            reasons.append(f"scope missing marker: {marker}")
    if '"provider": "yahoo_finance_via_yfinance"' not in licensing:
        reasons.append("licensing policy does not bind Yahoo expectation payloads")
    if '"function": "EARNINGS_ESTIMATES"' in collector:
        reasons.append("collector still uses Alpha Vantage for expectation history")
    if collector.count('"function": "NEWS_SENTIMENT"') != 1:
        reasons.append("collector recognition operation is not exact")
    if '"alpha_vantage_request_count": 12' not in collector:
        reasons.append("collector does not record the 12-call Alpha Vantage bound")
    if 'EXPECTED_YFINANCE_VERSION = "1.5.1"' not in helper:
        reasons.append("Yahoo expectation helper version is not pinned")
    return not reasons, reasons


def merge_target_pr(token: str, pr_number: int) -> None:
    base.run_command(
        ["gh", "pr", "ready", str(pr_number), "--repo", base.TARGET_REPOSITORY],
        env={"GH_TOKEN": token},
    )
    base.run_command(
        ["gh", "pr", "merge", str(pr_number), "--repo", base.TARGET_REPOSITORY, "--squash", "--delete-branch=false"],
        env={"GH_TOKEN": token},
    )


def should_dispatch_public(token: str, main_sha: str) -> tuple[bool, str]:
    runs = base.list_workflow_runs(base.TARGET_REPOSITORY, base.PUBLIC_WORKFLOW, token)
    same_revision = [run for run in runs if str(run.get("head_sha", "")).lower() == main_sha.lower()]

    for run in same_revision:
        if run.get("status") in {"queued", "in_progress", "waiting", "pending"}:
            return False, f"public collection run {run.get('id')} is already {run.get('status')} for current main"
    for run in same_revision:
        if run.get("status") == "completed" and run.get("conclusion") == "success":
            return False, f"public collection run {run.get('id')} already succeeded for current main"

    cutoff = base.utc_now() - timedelta(hours=24)

    # Provider quota/cooldown is repository-wide, not commit-scoped. A migration-only
    # commit must not reset the collection window and immediately repeat 25 MarketData
    # calls. Any recent terminal collection run therefore holds provider execution for
    # 24 hours, even if main advanced, while the controller may continue safe code/CI
    # reconciliation. This does not affect exact-head validation or private CI.
    recent_terminal = [
        run for run in runs
        if run.get("status") == "completed"
        and run.get("conclusion") in {"success", "failure", "cancelled", "timed_out"}
        and isinstance(run.get("created_at"), str)
        and base.parse_github_time(run["created_at"]) >= cutoff
    ]
    if recent_terminal:
        latest = recent_terminal[0]
        return False, (
            f"provider cooldown active for 24 hours after public run {latest.get('id')} "
            f"({latest.get('conclusion')}); code revision does not reset provider quota window"
        )

    return True, "no active collection and provider cooldown expired"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run PPI migration autopilot with dynamic target updates")
    parser.add_argument("--output-root", required=True)
    args = parser.parse_args()

    token = os.environ.get("RAW_TOKEN", "").strip()
    base.require(bool(token), "RAW_TOKEN is not configured")
    alpha_key = os.environ.get("PPI_ALPHA_VANTAGE_API_KEY", "").strip()
    marketdata_token = os.environ.get("PPI_MARKETDATA_TOKEN", "").strip()

    actions: list[str] = []
    blocked: list[str] = []
    login = base.authenticated_login(token)
    target_metadata = base.verify_repository(base.TARGET_REPOSITORY, base.TARGET_REPOSITORY_ID, token)
    private_metadata = base.verify_repository(base.PRIVATE_REPOSITORY, base.PRIVATE_REPOSITORY_ID, token)
    base.require(target_metadata.get("visibility") == "public", "acquisition repository must remain public")
    base.require(private_metadata.get("visibility") == "private", "analysis repository must remain private")
    target_permission = base.collaborator_permission(base.TARGET_REPOSITORY, login, token)
    private_permission = base.collaborator_permission(base.PRIVATE_REPOSITORY, login, token)

    base.run_bootstrap(token)
    actions.append("Synchronized the exact reviewed acquisition template into the target update branch.")

    try:
        base.sync_secret(base.TARGET_REPOSITORY, "PPI_PRIVATE_HANDOFF_TOKEN", token, token)
        actions.append("Synchronized the private-handoff token into the acquisition repository.")
    except Exception as exc:
        blocked.append(f"Could not synchronize PPI_PRIVATE_HANDOFF_TOKEN: {exc}")

    target_secret_names, target_secret_error = list_target_secret_names(token)
    if target_secret_names is not None:
        actions.append("Read the acquisition secret-name inventory without reading secret values.")
    elif target_secret_error:
        actions.append("Could not enumerate target secret names; provider readiness will be tested by the collector.")

    provider_ready = True
    for name, value, label in (
        ("PPI_ALPHA_VANTAGE_API_KEY", alpha_key, "Alpha Vantage"),
        ("PPI_MARKETDATA_TOKEN", marketdata_token, "MarketData"),
    ):
        if value:
            try:
                base.sync_secret(base.TARGET_REPOSITORY, name, value, token)
                actions.append(f"Synchronized the {label} credential into the acquisition repository.")
            except Exception as exc:
                blocked.append(f"Could not synchronize {name}: {exc}")
                provider_ready = False
        elif target_secret_names is not None and name in target_secret_names:
            actions.append(f"Confirmed an existing {name} secret in the acquisition repository.")
        elif target_secret_names is not None:
            blocked.append(f"{name} is absent from both source and acquisition repositories.")
            provider_ready = False
        else:
            actions.append(f"{name} source copy is absent; the collector will fail fast if the target copy is also absent.")

    pr = current_target_pr(token)
    gate_ref = base.TARGET_BRANCH if pr else "main"
    gate_ready, gate_reasons = target_gate(token, gate_ref)
    blocked.extend(gate_reasons)
    if gate_ready and pr:
        pr_number = int(pr.get("number", 0) or 0)
        base.require(pr_number > 0, "target update PR number is invalid")
        merge_target_pr(token, pr_number)
        actions.append(f"Merged acquisition update PR {pr_number} after all machine gates passed.")
    elif gate_ready:
        actions.append("Acquisition main already satisfies the current machine gates.")

    main_sha = target_main_sha(token)
    target_main_ready = base.workflow_exists(base.TARGET_REPOSITORY, base.PUBLIC_WORKFLOW, "main", token)
    public_runs_before = base.list_workflow_runs(base.TARGET_REPOSITORY, base.PUBLIC_WORKFLOW, token) if target_main_ready else []
    latest_public_before = public_runs_before[0] if public_runs_before else None

    if target_main_ready and gate_ready and provider_ready and not blocked:
        dispatch, reason = should_dispatch_public(token, main_sha)
        if dispatch:
            request_id = base.dispatch_public_collection(token)
            actions.append(f"Dispatched public collection with request ID {request_id}.")
        else:
            actions.append(reason)
    elif not target_main_ready:
        blocked.append("Public collector is not installed on acquisition/main yet.")

    public_runs_after = base.list_workflow_runs(base.TARGET_REPOSITORY, base.PUBLIC_WORKFLOW, token) if target_main_ready else []
    latest_public = public_runs_after[0] if public_runs_after else latest_public_before
    if latest_public:
        actions.append(f"Latest public collection run {latest_public.get('id')} is {latest_public.get('status')} with conclusion {latest_public.get('conclusion')}.")

    successful_public = base.latest_successful_public_run(token)
    private_exists = base.workflow_exists(base.PRIVATE_REPOSITORY, base.PRIVATE_WORKFLOW, "main", token)
    private_runs_before = base.list_workflow_runs(base.PRIVATE_REPOSITORY, base.PRIVATE_WORKFLOW, token) if private_exists else []
    if successful_public:
        dispatched, detail = base.dispatch_private_if_ready(token, successful_public)
        actions.append(detail)
        if not dispatched and "not installed" in detail:
            blocked.append(detail)
    private_runs_after = base.list_workflow_runs(base.PRIVATE_REPOSITORY, base.PRIVATE_WORKFLOW, token) if private_exists else []
    latest_private = private_runs_after[0] if private_runs_after else (private_runs_before[0] if private_runs_before else None)
    if latest_private:
        actions.append(f"Latest private final-analysis run {latest_private.get('id')} is {latest_private.get('status')} with conclusion {latest_private.get('conclusion')}.")

    report = {
        "schema_version": "2.1.0",
        "status": "blocked" if blocked else "progressed",
        "token_login": login,
        "target_permission": target_permission,
        "private_permission": private_permission,
        "actions": actions,
        "blocked_reasons": sorted(set(blocked)),
        "public_workflow": run_summary(latest_public),
        "private_workflow": run_summary(latest_private),
        "run": {
            "repository": os.environ.get("GITHUB_REPOSITORY", ""),
            "run_id": os.environ.get("GITHUB_RUN_ID", ""),
            "attempt": os.environ.get("GITHUB_RUN_ATTEMPT", ""),
            "head_sha": os.environ.get("GITHUB_SHA", ""),
            "event": os.environ.get("GITHUB_EVENT_NAME", ""),
            "generated_at_utc": base.utc_now().replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        },
        "authority": {
            "bootstrap_sync": True,
            "target_secret_sync": True,
            "target_pr_merge_after_machine_gates": True,
            "public_collection_dispatch": True,
            "private_final_analysis_dispatch": True,
            "registry_mutation": False,
            "production": False,
            "publication": False,
            "broker": False,
            "orders": False,
            "trading": False,
            "mmm_raw_data": False,
            "r12": False,
        },
    }
    base.write_report(Path(args.output_root), report)
    print(json.dumps({"status": report["status"], "blocked_reasons": report["blocked_reasons"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"autopilot v2 failed: {exc}", file=__import__("sys").stderr)
        raise SystemExit(1)
