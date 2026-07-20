from __future__ import annotations

import argparse
import json
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any

WORKFLOW_PATH = ".github/workflows/verify-primary-source-coverage.yml"
SLOT_TIMES = (time(1, 15), time(7, 15), time(13, 15), time(19, 15))
ALLOWED_EVENTS = {"schedule", "workflow_dispatch"}
ALLOWED_STATUSES = {"queued", "in_progress", "completed"}


class WatchdogError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise WatchdogError(message)


def parse_utc(value: str) -> datetime:
    text = str(value).strip()
    require(bool(text), "UTC timestamp is required")
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise WatchdogError("invalid UTC timestamp") from exc
    require(parsed.tzinfo is not None, "UTC timestamp must include a timezone")
    return parsed.astimezone(timezone.utc)


def previous_weekday(value: datetime) -> datetime:
    candidate = value - timedelta(days=1)
    while candidate.weekday() >= 5:
        candidate -= timedelta(days=1)
    return candidate


def expected_slot(now: datetime) -> datetime:
    now = now.astimezone(timezone.utc)
    if now.weekday() < 5:
        candidates = [datetime.combine(now.date(), slot, tzinfo=timezone.utc) for slot in SLOT_TIMES]
        eligible = [slot for slot in candidates if slot <= now]
        if eligible:
            return max(eligible)
    prior = previous_weekday(now)
    return datetime.combine(prior.date(), SLOT_TIMES[-1], tzinfo=timezone.utc)


def matching_runs(history: dict[str, Any], *, slot: datetime, now: datetime) -> list[dict[str, Any]]:
    values = history.get("workflow_runs")
    require(isinstance(values, list), "workflow run history is missing")
    lower = slot - timedelta(minutes=5)
    upper = now + timedelta(minutes=5)
    matches: list[dict[str, Any]] = []
    for value in values:
        if not isinstance(value, dict):
            continue
        try:
            created = parse_utc(str(value.get("created_at", "")))
        except WatchdogError:
            continue
        if not (lower <= created <= upper):
            continue
        if value.get("path") != WORKFLOW_PATH:
            continue
        if value.get("head_branch") != "main":
            continue
        if value.get("event") not in ALLOWED_EVENTS:
            continue
        if value.get("status") not in ALLOWED_STATUSES:
            continue
        matches.append(value)
    return sorted(matches, key=lambda item: int(item.get("id", 0)))


def evaluate(history: dict[str, Any], *, now_utc: str) -> dict[str, Any]:
    now = parse_utc(now_utc)
    slot = expected_slot(now)
    matches = matching_runs(history, slot=slot, now=now)
    return {
        "schema_version": "1.0.0",
        "status": "covered" if matches else "dispatch_required",
        "dispatch_required": not matches,
        "expected_slot_utc": slot.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "evaluated_at_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "matching_run_ids": [int(item["id"]) for item in matches],
        "workflow_path": WORKFLOW_PATH,
        "dispatch_ref": "main",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Plan bounded recovery for a missed primary-source schedule slot")
    parser.add_argument("--history", type=Path, required=True)
    parser.add_argument("--now", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        history = json.loads(args.history.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise WatchdogError("cannot read valid workflow history") from exc
    require(isinstance(history, dict), "workflow history must be an object")
    result = evaluate(history, now_utc=args.now)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except WatchdogError as exc:
        raise SystemExit(str(exc)) from exc
