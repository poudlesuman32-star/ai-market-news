#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

import ppi_migration_autopilot as base


def list_target_secret_names(token: str) -> tuple[set[str] | None, str | None]:
    try:
        raw = base.run_command(
            ["gh", "secret", "list", "--repo", base.TARGET_REPOSITORY, "--json", "name"],
            env={"GH_TOKEN": token},
        )
        value = json.loads(raw or "[]")
        base.require(isinstance(value, list), "target secret list is not an array")
        names = {
            str(item.get("name", ""))
            for item in value
            if isinstance(item, dict) and isinstance(item.get("name"), str)
        }
        return names, None
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Run PPI migration autopilot with existing-target-secret discovery")
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
    actions.append("Synchronized the reviewed acquisition template and target PR branch.")

    try:
        base.sync_secret(base.TARGET_REPOSITORY, "PPI_PRIVATE_HANDOFF_TOKEN", token, token)
        actions.append("Synchronized the private-handoff token into the acquisition repository.")
    except Exception as exc:
        blocked.append(f"Could not synchronize PPI_PRIVATE_HANDOFF_TOKEN: {exc}")

    target_secret_names, target_secret_error = list_target_secret_names(token)
    if target_secret_names is not None:
        actions.append("Read the acquisition repository secret-name inventory without reading secret values.")
    elif target_secret_error:
        actions.append("Could not enumerate target secret names; provider readiness will be tested by the public collector.")

    provider_ready = True
    if alpha_key:
        try:
            base.sync_secret(base.TARGET_REPOSITORY, "PPI_ALPHA_VANTAGE_API_KEY", alpha_key, token)
            actions.append("Synchronized the Alpha Vantage credential into the acquisition repository.")
        except Exception as exc:
            blocked.append(f"Could not synchronize PPI_ALPHA_VANTAGE_API_KEY: {exc}")
            provider_ready = False
    elif target_secret_names is not None and "PPI_ALPHA_VANTAGE_API_KEY" in target_secret_names:
        actions.append("Confirmed an existing PPI_ALPHA_VANTAGE_API_KEY secret in the acquisition repository.")
    elif target_secret_names is not None:
        blocked.append("PPI_ALPHA_VANTAGE_API_KEY is absent from both the source and acquisition repositories.")
        provider_ready = False
    else:
        actions.append("PPI_ALPHA_VANTAGE_API_KEY source copy is absent; the collector will fail fast if the target copy is also absent.")

    if marketdata_token:
        try:
            base.sync_secret(base.TARGET_REPOSITORY, "PPI_MARKETDATA_TOKEN", marketdata_token, token)
            actions.append("Synchronized the MarketData credential into the acquisition repository.")
        except Exception as exc:
            blocked.append(f"Could not synchronize PPI_MARKETDATA_TOKEN: {exc}")
            provider_ready = False
    elif target_secret_names is not None and "PPI_MARKETDATA_TOKEN" in target_secret_names:
        actions.append("Confirmed an existing PPI_MARKETDATA_TOKEN secret in the acquisition repository.")
    elif target_secret_names is not None:
        blocked.append("PPI_MARKETDATA_TOKEN is absent from both the source and acquisition repositories.")
        provider_ready = False
    else:
        actions.append("PPI_MARKETDATA_TOKEN source copy is absent; the collector will fail fast if the target copy is also absent.")

    gate_ready, gate_reasons = base.target_gate(token)
    blocked.extend(gate_reasons)
    if gate_ready:
        _, pr = base.api("GET", f"/repos/{base.TARGET_REPOSITORY}/pulls/{base.TARGET_PR}", token=token)
        if isinstance(pr, dict) and pr.get("state") == "open":
            base.mark_ready_and_merge(token)
            actions.append("Marked target PR 1 ready and merged it after all machine gates passed.")
        else:
            actions.append("Target acquisition changes are already merged.")

    target_main_ready = base.workflow_exists(base.TARGET_REPOSITORY, base.PUBLIC_WORKFLOW, "main", token)
    public_runs_before = base.list_workflow_runs(base.TARGET_REPOSITORY, base.PUBLIC_WORKFLOW, token) if target_main_ready else []
    latest_public_before = public_runs_before[0] if public_runs_before else None

    dispatch_blockers = bool(blocked) or not provider_ready
    if target_main_ready and gate_ready and not dispatch_blockers:
        dispatch, reason = base.should_dispatch_public(token)
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
        actions.append(
            "Latest public collection run "
            f"{latest_public.get('id')} is {latest_public.get('status')} "
            f"with conclusion {latest_public.get('conclusion')}."
        )

    successful_public = base.latest_successful_public_run(token)
    private_runs_before = base.list_workflow_runs(base.PRIVATE_REPOSITORY, base.PRIVATE_WORKFLOW, token) if base.workflow_exists(base.PRIVATE_REPOSITORY, base.PRIVATE_WORKFLOW, "main", token) else []
    if successful_public:
        dispatched, detail = base.dispatch_private_if_ready(token, successful_public)
        actions.append(detail)
        if not dispatched and "not installed" in detail:
            blocked.append(detail)
    private_runs_after = base.list_workflow_runs(base.PRIVATE_REPOSITORY, base.PRIVATE_WORKFLOW, token) if base.workflow_exists(base.PRIVATE_REPOSITORY, base.PRIVATE_WORKFLOW, "main", token) else []
    latest_private = private_runs_after[0] if private_runs_after else (private_runs_before[0] if private_runs_before else None)
    if latest_private:
        actions.append(
            "Latest private final-analysis run "
            f"{latest_private.get('id')} is {latest_private.get('status')} "
            f"with conclusion {latest_private.get('conclusion')}."
        )

    report = {
        "schema_version": "2.0.0",
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
