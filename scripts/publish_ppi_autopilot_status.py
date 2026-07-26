#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

API_ROOT = "https://api.github.com"
SOURCE_REPOSITORY = "poudlesuman32-star/ai-market-news"
SOURCE_REPOSITORY_ID = 1290414659
STATUS_ISSUE = 83
MAX_ITEM_LENGTH = 1200


class StatusError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise StatusError(message)


def api(method: str, path: str, *, token: str, payload: dict[str, Any] | None = None) -> Any:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = Request(
        API_ROOT + path,
        data=body,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "PPI migration autopilot status publisher",
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
        raise StatusError(f"GitHub API network failure for {method} {path}: {exc}") from exc
    try:
        value: Any = json.loads(raw.decode("utf-8")) if raw else None
    except (UnicodeDecodeError, json.JSONDecodeError):
        value = raw.decode("utf-8", errors="replace")
    if status not in {200, 201}:
        detail = value.get("message") if isinstance(value, dict) else value
        raise StatusError(f"GitHub API {method} {path} returned {status}: {detail}")
    return value


def clean_text(value: Any, *, token: str) -> str:
    text = str(value or "")[:MAX_ITEM_LENGTH]
    for marker in (token, "ghp_", "github_pat_", "ghs_", "Bearer "):
        if marker:
            text = text.replace(marker, "[REDACTED]")
    return text


def render(report: dict[str, Any], *, token: str) -> str:
    authority = report.get("authority")
    require(isinstance(authority, dict), "autopilot report authority is missing")
    for key in ("registry_mutation", "production", "publication", "broker", "orders", "trading", "mmm_raw_data", "r12"):
        require(authority.get(key) is False, f"dangerous authority unexpectedly enabled: {key}")

    run = report.get("run") if isinstance(report.get("run"), dict) else {}
    lines = [
        "# PPI migration autopilot status",
        "",
        f"- Status: **{clean_text(report.get('status'), token=token)}**",
        f"- Updated: `{clean_text(run.get('generated_at_utc'), token=token)}`",
        f"- Autopilot run: `{clean_text(run.get('run_id'), token=token)}` attempt `{clean_text(run.get('attempt'), token=token)}`",
        f"- Event: `{clean_text(run.get('event'), token=token)}`",
        f"- Source head: `{clean_text(run.get('head_sha'), token=token)}`",
        f"- Token login: `{clean_text(report.get('token_login'), token=token)}`",
        f"- Acquisition permission: `{clean_text(report.get('target_permission'), token=token)}`",
        f"- Private permission: `{clean_text(report.get('private_permission'), token=token)}`",
        "",
        "## Actions",
        "",
    ]
    actions = report.get("actions") if isinstance(report.get("actions"), list) else []
    lines.extend(f"- {clean_text(item, token=token)}" for item in actions)
    if not actions:
        lines.append("- No action recorded.")

    blocked = report.get("blocked_reasons") if isinstance(report.get("blocked_reasons"), list) else []
    lines.extend(["", "## Blocked reasons", ""])
    if blocked:
        lines.extend(f"- {clean_text(item, token=token)}" for item in blocked)
    else:
        lines.append("- None.")

    lines.extend([
        "",
        "## Safety boundary",
        "",
        "Provider credentials and raw provider payloads are never written to this issue. Registry, production, publication, broker, order, trading, MMM/raw-data, and R12 authority remain disabled in the public autopilot.",
        "",
        "This issue is replaced automatically on every reconciliation run.",
    ])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Publish a sanitized PPI autopilot report to the canonical status issue")
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    token = os.environ.get("RAW_TOKEN", "").strip()
    require(token, "RAW_TOKEN is not configured")
    report = json.loads(args.report.read_text(encoding="utf-8"))
    require(isinstance(report, dict), "autopilot report must be an object")

    repository = api("GET", f"/repos/{SOURCE_REPOSITORY}", token=token)
    require(isinstance(repository, dict), "source repository response is invalid")
    require(int(repository.get("id", 0)) == SOURCE_REPOSITORY_ID, "source repository ID drift")
    require(repository.get("visibility") == "public" and repository.get("archived") is False, "source repository boundary mismatch")

    issue = api("GET", f"/repos/{SOURCE_REPOSITORY}/issues/{STATUS_ISSUE}", token=token)
    require(isinstance(issue, dict) and issue.get("pull_request") is None, "status issue identity mismatch")
    require(issue.get("state") == "open", "status issue is not open")

    body = render(report, token=token)
    api(
        "PATCH",
        f"/repos/{SOURCE_REPOSITORY}/issues/{STATUS_ISSUE}",
        token=token,
        payload={"title": "PPI migration autopilot status", "body": body},
    )
    print(json.dumps({"status": "published", "issue": STATUS_ISSUE}, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except StatusError as exc:
        raise SystemExit(str(exc)) from exc
