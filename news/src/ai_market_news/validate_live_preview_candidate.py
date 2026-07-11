from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from .collector_common import CollectorError, require

VALIDATOR_VERSION = "live-preview-independent-v1"
REQUIRED_PROVIDERS = ("sec_edgar", "official_company_source")
SUPPORTED_EVENTS = ("workflow_dispatch", "schedule")
FORBIDDEN_PUBLIC_FIELDS = {
    "score",
    "rank",
    "portfolio",
    "watchlist",
    "recommendation",
    "position_size",
    "credentials",
    "api_key",
    "private_notes",
    "private_evidence",
    "internal_score",
}


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CollectorError(f"cannot read valid JSON: {path}") from exc
    require(isinstance(value, dict), f"expected JSON object: {path}")
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise CollectorError(f"cannot read news dataset: {path}") from exc
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise CollectorError(f"{path}:{line_number}: invalid JSON") from exc
        require(isinstance(value, dict), f"{path}:{line_number}: expected object")
        records.append(value)
    return records


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def validate_live_preview_candidate(
    *,
    news_path: Path,
    receipt_path: Path,
    manifest_path: Path,
    report_path: Path,
) -> dict[str, Any]:
    records = read_jsonl(news_path)
    receipt = read_json(receipt_path)
    manifest = read_json(manifest_path)
    report = read_json(report_path)

    dataset_hash = sha256_file(news_path)
    provider_counts: dict[str, int] = {}
    record_ids: list[str] = []
    event_ids: set[str] = set()
    private_fields: set[str] = set()
    records_valid = True
    primary_sources_only = True
    synthetic_absent = True
    source_unmodified = True

    for record in records:
        provider = str(record.get("provider", ""))
        provider_counts[provider] = provider_counts.get(provider, 0) + 1
        record_ids.append(str(record.get("record_id", "")))
        event_ids.add(str(record.get("event_id", "")))
        private_fields.update(FORBIDDEN_PUBLIC_FIELDS.intersection(record))
        records_valid = records_valid and record.get("validation") == "transformed_valid"
        primary_sources_only = primary_sources_only and record.get("primary_source") is True
        synthetic_absent = synthetic_absent and record.get("synthetic_content_used") is False
        source_unmodified = source_unmodified and record.get("source_content_modified") is False

    workflow_event = str(report.get("workflow_event", ""))
    expected_schedule_flag = workflow_event == "schedule"
    receipt_counts = receipt.get("provider_counts")
    manifest_counts = manifest.get("provider_counts")
    request_counts = receipt.get("request_counts")
    gate_checks = report.get("live_primary_countability_checks")

    checks = {
        "supported_read_only_trigger": workflow_event in SUPPORTED_EVENTS,
        "schedule_flag_matches_trigger": report.get("schedule_enabled") is expected_schedule_flag,
        "collection_mode_live_primary_sources": receipt.get("collection_mode") == "live_primary_sources" == report.get("collection_mode"),
        "source_repository_consistent": receipt.get("source_repository") == manifest.get("source_repository") == "poudlesuman32-star/ai-market-news",
        "source_commit_consistent": receipt.get("source_commit") == manifest.get("source_commit") == report.get("source_commit"),
        "run_id_consistent": receipt.get("run_id") == report.get("run_id"),
        "snapshot_path_consistent": manifest.get("snapshot_path") == f"snapshots/{receipt.get('run_id')}",
        "dataset_hash_consistent": receipt.get("dataset_sha256") == manifest.get("file_sha256") == dataset_hash,
        "record_count_consistent": receipt.get("record_count") == manifest.get("record_count") == report.get("accepted_event_count") == len(records),
        "event_count_consistent": receipt.get("event_count") == manifest.get("event_count") == len(event_ids),
        "provider_counts_consistent": isinstance(receipt_counts, dict) and receipt_counts == manifest_counts == provider_counts,
        "record_ids_unique_and_present": bool(record_ids) and all(record_ids) and len(record_ids) == len(set(record_ids)),
        "event_ids_present": bool(event_ids) and all(event_ids),
        "records_transformed_valid": records_valid,
        "primary_sources_only": primary_sources_only,
        "synthetic_content_absent": synthetic_absent and receipt.get("synthetic_content_used") is False and manifest.get("synthetic_content_used") is False,
        "source_content_unmodified": source_unmodified and receipt.get("source_content_modified") is False and manifest.get("source_content_modified") is False,
        "private_content_excluded": not private_fields and receipt.get("private_content_excluded") is True and manifest.get("private_content_excluded") is True,
        "sec_network_requests_recorded": isinstance(request_counts, dict) and int(request_counts.get("sec", 0)) > 0,
        "official_company_network_requests_recorded": isinstance(request_counts, dict) and int(request_counts.get("official_company_sources", 0)) > 0,
        "accepted_sec_record_present": provider_counts.get("sec_edgar", 0) > 0,
        "accepted_official_company_record_present": provider_counts.get("official_company_source", 0) > 0,
        "provider_failures_empty": receipt.get("provider_failures") == [] and report.get("provider_failures") == [],
        "first_gate_passed": report.get("this_run_qualifies") is True and report.get("qualification_exclusion_reasons") == [] and isinstance(gate_checks, dict) and bool(gate_checks) and all(gate_checks.values()),
        "preview_only_manifest": manifest.get("publication_status") == "preview_only" and manifest.get("data_commit") is None and manifest.get("public_commit") is None,
        "publication_disabled": report.get("publication_enabled") is False and report.get("published_to_repository") is False,
        "contents_write_disabled": report.get("contents_write_permission_authorized") is False,
        "external_writes_disabled": report.get("external_writes_enabled") is False,
        "secrets_not_required": report.get("secrets_required") is False,
        "rejected_events_empty": int(report.get("rejected_event_count", -1)) == 0,
    }
    failures = sorted(name for name, passed in checks.items() if not passed)
    result = {
        "schema_version": "1.0.0",
        "validator_version": VALIDATOR_VERSION,
        "candidate_valid": not failures,
        "checks": checks,
        "failures": failures,
        "dataset_sha256": dataset_hash,
        "input_sha256": {
            "news.jsonl": dataset_hash,
            "collection_receipt.json": sha256_file(receipt_path),
            "news_manifest.preview.json": sha256_file(manifest_path),
            "run_report.json": sha256_file(report_path),
        },
        "record_count": len(records),
        "event_count": len(event_ids),
        "provider_counts": provider_counts,
        "workflow_event": workflow_event,
        "publication_authorized": False,
        "official_r9_count_authorized": False,
    }
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Independently validate a read-only live preview candidate")
    parser.add_argument("--news", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    result = validate_live_preview_candidate(
        news_path=args.news,
        receipt_path=args.receipt,
        manifest_path=args.manifest,
        report_path=args.report,
    )
    write_json_atomic(args.output, result)
    print(json.dumps(result, indent=2, sort_keys=True))
    if not result["candidate_valid"]:
        raise CollectorError("independent live preview validation failed: " + ", ".join(result["failures"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
