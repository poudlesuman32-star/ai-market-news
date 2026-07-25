#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

API_ROOT = "https://api.github.com"
TARGET_REPOSITORY = "spoudel2010-ux/ppi-data-acquisition"
TARGET_REPOSITORY_ID = 1312286476
TARGET_PR = 1
TARGET_BRANCH = "agent/bootstrap-r11-public-acquisition"
PRIVATE_REPOSITORY = "musksuman3/ai-signal-engine"
PRIVATE_REPOSITORY_ID = 1290626648
PUBLIC_WORKFLOW = "collect-r11-public-evidence.yml"
PRIVATE_WORKFLOW = "ppi-r11-private-final-analysis.yml"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def api(
    method: str,
    path: str,
    *,
    token: str,
    payload: dict[str, Any] | None = None,
    allowed_statuses: tuple[int, ...] = (200, 201, 204),
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
            "User-Agent": "PPI migration autopilot",
            **({"Content-Type": "application/json"} if body is not None else {}),
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
        raise RuntimeError(f"GitHub API network failure for {method} {path}: {exc}") from exc
    parsed: Any = None
    if raw:
        try:
            parsed = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            parsed = raw.decode("utf-8", errors="replace")
    if status not in allowed_statuses:
        message = parsed.get("message") if isinstance(parsed, dict) else str(parsed)
        raise RuntimeError(f"GitHub API {method} {path} returned {status}: {message}")
    return status, parsed


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_github_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def authenticated_login(token: str) -> str:
    _, value = api("GET", "/user", token=token)
    require(isinstance(value, dict), "unexpected authenticated-user response")
    login = value.get("login")
    require(isinstance(login, str) and login, "RAW_TOKEN did not resolve to a login")
    return login


def verify_repository(repository: str, repository_id: int, token: str) -> dict[str, Any]:
    _, value = api("GET", f"/repos/{repository}", token=token)
    require(isinstance(value, dict), f"unexpected repository response for {repository}")
    require(int(value.get("id", 0)) == repository_id, f"repository ID drift for {repository}")
    require(value.get("archived") is False, f"repository is archived: {repository}")
    return value


def collaborator_permission(repository: str, login: str, token: str) -> str:
    _, value = api(
        "GET",
        f"/repos/{repository}/collaborators/{quote(login, safe='')}/permission",
        token=token,
    )
    require(isinstance(value, dict), f"unexpected permission response for {repository}")
    permission = str(value.get("permission", ""))
    require(permission in {"write", "maintain", "admin"}, f"{login} lacks write access to {repository}: {permission!r}")
    return permission


def run_command(args: list[str], *, env: dict[str, str] | None = None, input_text: str | None = None) -> str:
    completed = subprocess.run(
        args,
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
        env={**os.environ, **(env or {})},
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"command failed ({completed.returncode}): {' '.join(args)}\n"
            f"stdout: {completed.stdout}\nstderr: {completed.stderr}"
        )
    return completed.stdout.strip()


def sync_secret(repository: str, name: str, value: str, token: str) -> None:
    require(bool(value), f"cannot synchronize empty secret {name}")
    run_command(
        ["gh", "secret", "set", name, "--repo", repository],
        env={"GH_TOKEN": token},
        input_text=value,
    )


def run_bootstrap(token: str) -> None:
    run_command(
        [sys.executable, "scripts/bootstrap_ppi_data_acquisition.py"],
        env={
            "PPI_CROSS_REPOSITORY_AUTOMATION": token,
            "TARGET_REPOSITORY": TARGET_REPOSITORY,
        },
    )


def fetch_text(repository: str, path: str, ref: str, token: str) -> str:
    _, value = api(
        "GET",
        f"/repos/{repository}/contents/{quote(path, safe='/')}?ref={quote(ref, safe='')}",
        token=token,
    )
    require(isinstance(value, dict), f"unexpected content response for {repository}:{path}")
    import base64

    content = value.get("content")
    require(value.get("encoding") == "base64" and isinstance(content, str), f"unexpected encoding for {path}")
    return base64.b64decode(content).decode("utf-8")


def target_gate(token: str) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    _, pr = api("GET", f"/repos/{TARGET_REPOSITORY}/pulls/{TARGET_PR}", token=token)
    require(isinstance(pr, dict), "unexpected target PR response")
    if pr.get("state") != "open":
        return bool(pr.get("merged_at")), reasons
    if (pr.get("head") or {}).get("ref") != TARGET_BRANCH:
        reasons.append("target PR head branch drift")
    if (pr.get("base") or {}).get("ref") != "main":
        reasons.append("target PR base branch drift")

    readme = fetch_text(TARGET_REPOSITORY, "README.md", TARGET_BRANCH, token)
    workflow = fetch_text(TARGET_REPOSITORY, ".github/workflows/collect-r11-public-evidence.yml", TARGET_BRANCH, token)
    contract_paths = (
        "contracts/PPI-R11-PUBLIC-ACQUISITION-003-R1.json",
        "contracts/PPI-PUBLIC-COLLECTOR-003-R1.json",
        "config/provider_licensing_dispositions.json",
    )
    for marker in (
        "Repository ID: `1312286476`",
        "exactly 50 retained paths",
        "PPI-R11-PUBLIC-ACQUISITION-003-R1",
        "public_storage_prohibited",
        "Do not merge the bootstrap PR until",
    ):
        if marker not in readme:
            reasons.append(f"README missing marker: {marker}")
    for marker in (
        "PRIVATE_RELEASE_HANDOFF_ENABLED: true",
        "ppi-r11-public-success-",
        "ppi-r11-public-failure-",
        "actions/checkout@",
        "persist-credentials: false",
    ):
        if marker not in workflow:
            reasons.append(f"collector workflow missing marker: {marker}")
    if "actions/checkout@v" in workflow or "actions/upload-artifact@v" in workflow:
        reasons.append("collector workflow contains mutable action tags")
    for path in contract_paths:
        try:
            fetch_text(TARGET_REPOSITORY, path, TARGET_BRANCH, token)
        except Exception:
            reasons.append(f"target branch missing {path}")
    return not reasons, reasons


def mark_ready_and_merge(token: str) -> str:
    run_command(
        ["gh", "pr", "ready", str(TARGET_PR), "--repo", TARGET_REPOSITORY],
        env={"GH_TOKEN": token},
    )
    output = run_command(
        ["gh", "pr", "merge", str(TARGET_PR), "--repo", TARGET_REPOSITORY, "--squash", "--delete-branch=false"],
        env={"GH_TOKEN": token},
    )
    return output


def workflow_exists(repository: str, path: str, ref: str, token: str) -> bool:
    status, _ = api(
        "GET",
        f"/repos/{repository}/contents/.github/workflows/{quote(path, safe='')}?ref={quote(ref, safe='')}",
        token=token,
        allowed_statuses=(200, 404),
    )
    return status == 200


def list_workflow_runs(repository: str, workflow: str, token: str) -> list[dict[str, Any]]:
    status, value = api(
        "GET",
        f"/repos/{repository}/actions/workflows/{quote(workflow, safe='')}/runs?branch=main&per_page=30",
        token=token,
        allowed_statuses=(200, 404),
    )
    if status == 404:
        return []
    require(isinstance(value, dict) and isinstance(value.get("workflow_runs"), list), "unexpected workflow-runs response")
    return [item for item in value["workflow_runs"] if isinstance(item, dict)]


def dispatch_public_collection(token: str) -> str:
    request_id = f"r11-batch3-{os.environ.get('GITHUB_RUN_ID', '00000000')[-8:].rjust(8, '0')}"
    api(
        "POST",
        f"/repos/{TARGET_REPOSITORY}/actions/workflows/{PUBLIC_WORKFLOW}/dispatches",
        token=token,
        payload={
            "ref": "main",
            "inputs": {
                "confirmation": "COLLECT-R11-BATCH-3",
                "request_id": request_id,
            },
        },
        allowed_statuses=(204,),
    )
    return request_id


def should_dispatch_public(token: str) -> tuple[bool, str]:
    runs = list_workflow_runs(TARGET_REPOSITORY, PUBLIC_WORKFLOW, token)
    now = utc_now()
    recent = [
        run
        for run in runs
        if isinstance(run.get("created_at"), str)
        and parse_github_time(run["created_at"]) >= now - timedelta(hours=24)
    ]
    if any(run.get("status") in {"queued", "in_progress", "waiting", "pending"} for run in recent):
        return False, "public collection already active"
    if any(run.get("conclusion") == "success" for run in recent):
        return False, "successful public collection already exists in the last 24 hours"
    failures = sum(run.get("conclusion") == "failure" for run in recent)
    if failures >= 3:
        return False, "daily public collection retry ceiling reached"
    return True, "no active or successful recent public collection"


def latest_successful_public_run(token: str) -> dict[str, Any] | None:
    for run in list_workflow_runs(TARGET_REPOSITORY, PUBLIC_WORKFLOW, token):
        if run.get("status") == "completed" and run.get("conclusion") == "success":
            return run
    return None


def dispatch_private_if_ready(token: str, public_run: dict[str, Any]) -> tuple[bool, str]:
    if not workflow_exists(PRIVATE_REPOSITORY, PRIVATE_WORKFLOW, "main", token):
        return False, "private final-analysis workflow is not installed yet"
    runs = list_workflow_runs(PRIVATE_REPOSITORY, PRIVATE_WORKFLOW, token)
    public_run_id = str(public_run.get("id", ""))
    if any(public_run_id and public_run_id in json.dumps(run, sort_keys=True) for run in runs[:20]):
        return False, "private analysis already exists for this public run"
    api(
        "POST",
        f"/repos/{PRIVATE_REPOSITORY}/actions/workflows/{PRIVATE_WORKFLOW}/dispatches",
        token=token,
        payload={
            "ref": "main",
            "inputs": {
                "public_run_id": public_run_id,
                "public_head_sha": str(public_run.get("head_sha", "")),
            },
        },
        allowed_statuses=(204,),
    )
    return True, f"dispatched private analysis for public run {public_run_id}"


def write_report(output_root: Path, report: dict[str, Any]) -> None:
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "autopilot.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# PPI migration autopilot",
        "",
        f"- Status: **{report['status']}**",
        f"- Token login: `{report['token_login']}`",
        f"- Target permission: `{report['target_permission']}`",
        f"- Private permission: `{report['private_permission']}`",
        "",
        "## Actions",
        "",
    ]
    for item in report["actions"]:
        lines.append(f"- {item}")
    if report["blocked_reasons"]:
        lines.extend(["", "## Blocked reasons", ""])
        lines.extend(f"- {item}" for item in report["blocked_reasons"])
    lines.extend([
        "",
        "Production, publication, broker, order, trading, MMM/raw-data, and R12 authority remain disabled.",
        "",
    ])
    (output_root / "autopilot.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the idempotent PPI migration autopilot")
    parser.add_argument("--output-root", required=True)
    args = parser.parse_args()

    token = os.environ.get("RAW_TOKEN", "").strip()
    require(bool(token), "RAW_TOKEN is not configured")
    alpha_key = os.environ.get("PPI_ALPHA_VANTAGE_API_KEY", "").strip()
    marketdata_token = os.environ.get("PPI_MARKETDATA_TOKEN", "").strip()

    actions: list[str] = []
    blocked: list[str] = []
    login = authenticated_login(token)
    target_metadata = verify_repository(TARGET_REPOSITORY, TARGET_REPOSITORY_ID, token)
    private_metadata = verify_repository(PRIVATE_REPOSITORY, PRIVATE_REPOSITORY_ID, token)
    require(target_metadata.get("visibility") == "public", "acquisition repository must remain public")
    require(private_metadata.get("visibility") == "private", "analysis repository must remain private")
    target_permission = collaborator_permission(TARGET_REPOSITORY, login, token)
    private_permission = collaborator_permission(PRIVATE_REPOSITORY, login, token)

    run_bootstrap(token)
    actions.append("Synchronized the reviewed acquisition template and target PR branch.")

    try:
        sync_secret(TARGET_REPOSITORY, "PPI_PRIVATE_HANDOFF_TOKEN", token, token)
        actions.append("Synchronized the private-handoff token into the acquisition repository.")
    except Exception as exc:
        blocked.append(f"Could not synchronize PPI_PRIVATE_HANDOFF_TOKEN: {exc}")

    if alpha_key:
        try:
            sync_secret(TARGET_REPOSITORY, "PPI_ALPHA_VANTAGE_API_KEY", alpha_key, token)
            actions.append("Synchronized the Alpha Vantage credential into the acquisition repository.")
        except Exception as exc:
            blocked.append(f"Could not synchronize PPI_ALPHA_VANTAGE_API_KEY: {exc}")
    else:
        blocked.append("PPI_ALPHA_VANTAGE_API_KEY is not configured in ai-market-news secrets.")

    if marketdata_token:
        try:
            sync_secret(TARGET_REPOSITORY, "PPI_MARKETDATA_TOKEN", marketdata_token, token)
            actions.append("Synchronized the MarketData credential into the acquisition repository.")
        except Exception as exc:
            blocked.append(f"Could not synchronize PPI_MARKETDATA_TOKEN: {exc}")
    else:
        blocked.append("PPI_MARKETDATA_TOKEN is not configured in ai-market-news secrets.")

    gate_ready, gate_reasons = target_gate(token)
    blocked.extend(gate_reasons)
    if gate_ready:
        _, pr = api("GET", f"/repos/{TARGET_REPOSITORY}/pulls/{TARGET_PR}", token=token)
        if isinstance(pr, dict) and pr.get("state") == "open":
            mark_ready_and_merge(token)
            actions.append("Marked target PR 1 ready and merged it after all machine gates passed.")
        else:
            actions.append("Target acquisition changes are already merged.")

    target_main_ready = workflow_exists(TARGET_REPOSITORY, PUBLIC_WORKFLOW, "main", token)
    if target_main_ready and gate_ready and not blocked:
        dispatch, reason = should_dispatch_public(token)
        if dispatch:
            request_id = dispatch_public_collection(token)
            actions.append(f"Dispatched public collection with request ID {request_id}.")
        else:
            actions.append(reason)
    elif not target_main_ready:
        blocked.append("Public collector is not installed on acquisition/main yet.")

    public_run = latest_successful_public_run(token)
    if public_run:
        dispatched, detail = dispatch_private_if_ready(token, public_run)
        actions.append(detail)
        if not dispatched and "not installed" in detail:
            blocked.append(detail)

    report = {
        "schema_version": "1.0.0",
        "status": "blocked" if blocked else "progressed",
        "token_login": login,
        "target_permission": target_permission,
        "private_permission": private_permission,
        "actions": actions,
        "blocked_reasons": sorted(set(blocked)),
        "run": {
            "repository": os.environ.get("GITHUB_REPOSITORY", ""),
            "run_id": os.environ.get("GITHUB_RUN_ID", ""),
            "attempt": os.environ.get("GITHUB_RUN_ATTEMPT", ""),
            "head_sha": os.environ.get("GITHUB_SHA", ""),
            "event": os.environ.get("GITHUB_EVENT_NAME", ""),
            "generated_at_utc": utc_now().replace(microsecond=0).isoformat().replace("+00:00", "Z"),
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
    write_report(Path(args.output_root), report)
    print(json.dumps({"status": report["status"], "blocked_reasons": report["blocked_reasons"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"autopilot failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
