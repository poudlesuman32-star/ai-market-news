from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from .collector_common import CollectorError, require

SHA_RE = re.compile(r"^[a-f0-9]{40}$", re.IGNORECASE)
UTC_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
REQUIRED_ARTIFACTS = (
    "news.jsonl",
    "collection_receipt.json",
    "news_manifest.preview.json",
    "run_report.json",
)


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CollectorError(f"{path}: invalid JSON: {exc}") from exc
    require(isinstance(value, dict), f"{path}: expected a JSON object")
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def artifact_bundle_sha256(artifact_root: Path) -> str:
    digest = hashlib.sha256()
    for name in REQUIRED_ARTIFACTS:
        path = artifact_root / name
        require(path.is_file(), f"missing preview artifact: {name}")
        payload = path.read_bytes()
        digest.update(name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(len(payload)).encode("ascii"))
        digest.update(b"\0")
        digest.update(payload)
    return digest.hexdigest()


def validate_gate(gate: dict[str, Any]) -> None:
    require(gate.get("schema_version") == "1.1.0", "unsupported preview gate schema")
    require(gate.get("stage") == "PPI-R5", "unexpected preview gate stage")
    require(gate.get("phase") == "manual_preview", "unexpected preview gate phase")
    required = gate.get("required_successful_runs")
    require(required == 5, "preview gate must require exactly five successful runs")
    runs = gate.get("successful_runs")
    require(isinstance(runs, list), "successful_runs must be a list")
    run_keys: set[tuple[str, str]] = set()
    bundle_hashes: set[str] = set()
    for index, run in enumerate(runs):
        require(isinstance(run, dict), f"successful_runs[{index}] must be an object")
        run_id = str(run.get("workflow_run_id", ""))
        attempt = str(run.get("workflow_run_attempt", ""))
        require(run_id.isdigit() and int(run_id) > 0, f"successful_runs[{index}]: invalid workflow_run_id")
        require(attempt.isdigit() and int(attempt) > 0, f"successful_runs[{index}]: invalid workflow_run_attempt")
        key = (run_id, attempt)
        require(key not in run_keys, f"duplicate preview run evidence: {run_id}/{attempt}")
        run_keys.add(key)
        source_commit = str(run.get("source_commit", ""))
        require(SHA_RE.fullmatch(source_commit) is not None, f"successful_runs[{index}]: invalid source_commit")
        bundle_hash = str(run.get("artifact_bundle_sha256", ""))
        require(re.fullmatch(r"[a-f0-9]{64}", bundle_hash) is not None, f"successful_runs[{index}]: invalid artifact hash")
        require(bundle_hash not in bundle_hashes, "the same preview artifact bundle cannot satisfy the gate twice")
        bundle_hashes.add(bundle_hash)
        require(UTC_RE.fullmatch(str(run.get("recorded_at_utc", ""))) is not None, f"successful_runs[{index}]: invalid recorded_at_utc")

    recorded = gate.get("successful_runs_recorded")
    require(recorded == len(runs), "successful_runs_recorded does not match successful_runs")
    satisfied = len(runs) >= required
    require(gate.get("gate_satisfied") is satisfied, "gate_satisfied is inconsistent with recorded runs")

    review_approved = gate.get("review_approved")
    require(isinstance(review_approved, bool), "review_approved must be boolean")
    if review_approved:
        require(satisfied, "preview gate cannot be approved before five successful runs")
        require(bool(str(gate.get("approved_by", "")).strip()), "approved_by is required")
        require(UTC_RE.fullmatch(str(gate.get("approved_at_utc", ""))) is not None, "approved_at_utc is invalid")
    else:
        require(gate.get("approved_by") is None, "approved_by must be null before approval")
        require(gate.get("approved_at_utc") is None, "approved_at_utc must be null before approval")

    authorized = satisfied and review_approved
    require(gate.get("publication_authorized") is authorized, "publication_authorized is inconsistent")
    require(gate.get("contents_write_permission_authorized") is authorized, "contents write authorization is inconsistent")
    for field in (
        "schedule_authorized",
        "secrets_authorized",
        "external_writes_authorized",
    ):
        require(gate.get(field) is False, f"{field} must remain false")


def validate_preview_report(report: dict[str, Any]) -> None:
    required_false = (
        "publication_enabled",
        "contents_write_permission_authorized",
        "schedule_enabled",
        "secrets_required",
        "external_writes_enabled",
        "published_to_repository",
    )
    require(report.get("schema_version") == "1.1.0", "unsupported run report schema")
    require(report.get("stage") == "PPI-R5", "unexpected run report stage")
    require(report.get("phase") == "manual_preview", "unexpected run report phase")
    require(report.get("success") is True, "preview run was not successful")
    require(report.get("this_run_qualifies") is True, "preview run does not qualify")
    require(report.get("workflow_event") == "workflow_dispatch", "only workflow_dispatch runs qualify")
    run_id = str(report.get("workflow_run_id", ""))
    attempt = str(report.get("workflow_run_attempt", ""))
    require(run_id.isdigit() and int(run_id) > 0, "invalid workflow_run_id")
    require(attempt.isdigit() and int(attempt) > 0, "invalid workflow_run_attempt")
    require(SHA_RE.fullmatch(str(report.get("source_commit", ""))) is not None, "invalid source_commit")
    require(report.get("required_successful_preview_runs") == 5, "run report has wrong gate count")
    require(report.get("validation_result") == "passed", "preview validation did not pass")
    require(report.get("accepted_event_count", 0) > 0, "zero-event preview cannot satisfy the gate")
    require(report.get("rejected_event_count", 0) >= 0, "invalid rejected_event_count")
    require(report.get("duplicate_count", 0) >= 0, "invalid duplicate_count")
    require(report.get("runtime_seconds", 0) >= 0, "invalid runtime_seconds")
    failures = report.get("provider_failures")
    require(isinstance(failures, list), "provider_failures must be a list")
    require(not failures, "provider failures prevent the run from satisfying the gate")
    for field in required_false:
        require(report.get(field) is False, f"{field} must be false for preview evidence")


def record_preview_run(
    *,
    gate: dict[str, Any],
    report: dict[str, Any],
    artifact_bundle_hash: str,
    recorded_at_utc: str,
) -> dict[str, Any]:
    validate_gate(gate)
    validate_preview_report(report)
    require(UTC_RE.fullmatch(recorded_at_utc) is not None, "recorded_at_utc must use UTC Z form")

    entry = {
        "workflow_run_id": str(report["workflow_run_id"]),
        "workflow_run_attempt": str(report["workflow_run_attempt"]),
        "source_commit": str(report["source_commit"]),
        "run_id": str(report["run_id"]),
        "collection_mode": str(report["collection_mode"]),
        "artifact_bundle_sha256": artifact_bundle_hash,
        "accepted_event_count": int(report["accepted_event_count"]),
        "ticker_count": int(report["ticker_count"]),
        "recorded_at_utc": recorded_at_utc,
    }
    runs = list(gate["successful_runs"])
    key = (entry["workflow_run_id"], entry["workflow_run_attempt"])
    require(
        key not in {(str(item["workflow_run_id"]), str(item["workflow_run_attempt"])) for item in runs},
        "preview run is already recorded",
    )
    require(
        entry["artifact_bundle_sha256"] not in {str(item["artifact_bundle_sha256"]) for item in runs},
        "preview artifact bundle is already recorded",
    )
    runs.append(entry)
    runs.sort(key=lambda item: (int(item["workflow_run_id"]), int(item["workflow_run_attempt"])))
    updated = dict(gate)
    updated["successful_runs"] = runs
    updated["successful_runs_recorded"] = len(runs)
    updated["gate_satisfied"] = len(runs) >= int(updated["required_successful_runs"])
    updated["review_approved"] = False
    updated["approved_by"] = None
    updated["approved_at_utc"] = None
    updated["publication_authorized"] = False
    updated["contents_write_permission_authorized"] = False
    validate_gate(updated)
    return updated


def approve_gate(*, gate: dict[str, Any], approver: str, approved_at_utc: str) -> dict[str, Any]:
    validate_gate(gate)
    require(gate["gate_satisfied"] is True, "five successful preview runs have not been recorded")
    require(bool(approver.strip()), "approver is required")
    require(UTC_RE.fullmatch(approved_at_utc) is not None, "approved_at_utc must use UTC Z form")
    updated = dict(gate)
    updated["review_approved"] = True
    updated["approved_by"] = approver.strip()
    updated["approved_at_utc"] = approved_at_utc
    updated["publication_authorized"] = True
    updated["contents_write_permission_authorized"] = True
    validate_gate(updated)
    return updated


def require_publication_authorized(gate: dict[str, Any]) -> None:
    validate_gate(gate)
    require(gate["publication_authorized"] is True, "public-news publication is not authorized")
    require(gate["contents_write_permission_authorized"] is True, "contents write permission is not authorized")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate and update the PPI-R5 preview gate")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("--gate", type=Path, required=True)

    record_parser = subparsers.add_parser("record")
    record_parser.add_argument("--gate", type=Path, required=True)
    record_parser.add_argument("--artifacts", type=Path, required=True)
    record_parser.add_argument("--recorded-at", required=True)
    record_parser.add_argument("--output", type=Path, required=True)

    approve_parser = subparsers.add_parser("approve")
    approve_parser.add_argument("--gate", type=Path, required=True)
    approve_parser.add_argument("--approver", required=True)
    approve_parser.add_argument("--approved-at", required=True)
    approve_parser.add_argument("--output", type=Path, required=True)

    require_parser = subparsers.add_parser("require-publication")
    require_parser.add_argument("--gate", type=Path, required=True)

    args = parser.parse_args(argv)
    gate = load_json(args.gate)
    if args.command == "validate":
        validate_gate(gate)
    elif args.command == "record":
        artifact_hash = artifact_bundle_sha256(args.artifacts)
        report = load_json(args.artifacts / "run_report.json")
        write_json(
            args.output,
            record_preview_run(
                gate=gate,
                report=report,
                artifact_bundle_hash=artifact_hash,
                recorded_at_utc=args.recorded_at,
            ),
        )
    elif args.command == "approve":
        write_json(args.output, approve_gate(gate=gate, approver=args.approver, approved_at_utc=args.approved_at))
    else:
        require_publication_authorized(gate)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
