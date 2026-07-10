from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from .collector_common import CollectorError, require

COMMIT_RE = re.compile(r"^[a-f0-9]{40}$", re.IGNORECASE)
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


def load_news(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise CollectorError(f"{path}:{line_number}: invalid JSON: {exc}") from exc
        require(isinstance(value, dict), f"{path}:{line_number}: record must be an object")
        require(value.get("validation") == "transformed_valid", f"{path}:{line_number}: record is not transformed_valid")
        require(value.get("synthetic_content_used") is False, f"{path}:{line_number}: synthetic content is forbidden")
        require(value.get("source_content_modified") is False, f"{path}:{line_number}: modified source content is forbidden")
        leaked = FORBIDDEN_PUBLIC_FIELDS.intersection(value)
        require(not leaked, f"{path}:{line_number}: private fields detected: {sorted(leaked)}")
        records.append(value)
    record_ids = [str(record.get("record_id", "")) for record in records]
    require(len(record_ids) == len(set(record_ids)), "duplicate record_id detected in preview dataset")
    return records


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_preview_artifacts(
    *,
    news_path: Path,
    source_repository: str,
    source_commit: str,
    run_id: str,
    generated_at_utc: str,
    collection_mode: str,
    workflow_event: str = "workflow_dispatch",
    workflow_run_id: str = "1",
    workflow_run_attempt: str = "1",
    runtime_seconds: int = 0,
    sec_request_count: int = 0,
    company_request_count: int = 0,
    polygon_request_count: int = 0,
    finnhub_request_count: int = 0,
    raw_event_count: int | None = None,
    normalized_event_count: int | None = None,
    duplicate_count: int = 0,
    rejected_event_count: int = 0,
    provider_failures: list[str] | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    require(source_repository == "poudlesuman32-star/ai-market-news", "unexpected source repository")
    require(COMMIT_RE.fullmatch(source_commit) is not None, "source_commit must be a 40-character SHA")
    require(bool(run_id.strip()), "run_id is required")
    require(collection_mode in {"fixture", "live_primary_sources"}, "unsupported preview collection mode")
    require(workflow_event == "workflow_dispatch", "only workflow_dispatch preview runs are supported")
    require(str(workflow_run_id).isdigit() and int(workflow_run_id) > 0, "workflow_run_id must be a positive integer")
    require(str(workflow_run_attempt).isdigit() and int(workflow_run_attempt) > 0, "workflow_run_attempt must be a positive integer")
    for name, value in (
        ("runtime_seconds", runtime_seconds),
        ("sec_request_count", sec_request_count),
        ("company_request_count", company_request_count),
        ("polygon_request_count", polygon_request_count),
        ("finnhub_request_count", finnhub_request_count),
        ("duplicate_count", duplicate_count),
        ("rejected_event_count", rejected_event_count),
    ):
        require(int(value) >= 0, f"{name} cannot be negative")

    failures = sorted(set(provider_failures or []))
    records = load_news(news_path)
    providers = sorted({str(record["provider"]) for record in records})
    provider_counts = {
        provider: sum(1 for record in records if str(record["provider"]) == provider)
        for provider in providers
    }
    tickers = sorted({str(record["ticker"]) for record in records})
    event_ids = {str(record["event_id"]) for record in records}
    published = sorted(str(record["published_at_utc"]) for record in records)
    dataset_hash = sha256_file(news_path)
    raw_count = len(records) if raw_event_count is None else int(raw_event_count)
    normalized_count = len(records) if normalized_event_count is None else int(normalized_event_count)
    require(raw_count >= len(records), "raw_event_count cannot be less than accepted records")
    require(normalized_count >= len(records), "normalized_event_count cannot be less than accepted records")

    receipt = {
        "schema_version": "1.1.0",
        "run_id": run_id,
        "collection_mode": collection_mode,
        "source_repository": source_repository,
        "source_commit": source_commit,
        "generated_at_utc": generated_at_utc,
        "collection_complete": True,
        "record_count": len(records),
        "event_count": len(event_ids),
        "provider_count": len(providers),
        "provider_counts": provider_counts,
        "providers": providers,
        "tickers": tickers,
        "input_file": "news.jsonl",
        "dataset_sha256": dataset_hash,
        "request_counts": {
            "sec": int(sec_request_count),
            "official_company_sources": int(company_request_count),
            "polygon": int(polygon_request_count),
            "finnhub": int(finnhub_request_count),
        },
        "provider_failures": failures,
        "synthetic_content_used": False,
        "source_content_modified": False,
        "private_content_excluded": True,
    }
    manifest = {
        "schema_version": "1.1.0",
        "publication_status": "preview_only",
        "snapshot_path": f"snapshots/{run_id}",
        "source_repository": source_repository,
        "source_commit": source_commit,
        "data_commit": None,
        "public_commit": None,
        "file_path": "news.jsonl",
        "file_sha256": dataset_hash,
        "record_count": len(records),
        "event_count": len(event_ids),
        "ticker_count": len(tickers),
        "provider_count": len(providers),
        "provider_counts": provider_counts,
        "earliest_publication_utc": published[0] if published else None,
        "latest_publication_utc": published[-1] if published else None,
        "synthetic_content_used": False,
        "source_content_modified": False,
        "private_content_excluded": True,
    }
    qualifies = bool(records) and not failures and rejected_event_count == 0
    report = {
        "schema_version": "1.1.0",
        "stage": "PPI-R5",
        "phase": "manual_preview",
        "run_id": run_id,
        "workflow_run_id": str(workflow_run_id),
        "workflow_run_attempt": str(workflow_run_attempt),
        "workflow_event": workflow_event,
        "source_commit": source_commit,
        "collection_mode": collection_mode,
        "success": True,
        "this_run_qualifies": qualifies,
        "runtime_seconds": int(runtime_seconds),
        "sec_request_count": int(sec_request_count),
        "company_request_count": int(company_request_count),
        "polygon_request_count": int(polygon_request_count),
        "finnhub_request_count": int(finnhub_request_count),
        "raw_event_count": raw_count,
        "normalized_event_count": normalized_count,
        "duplicate_count": int(duplicate_count),
        "accepted_event_count": len(records),
        "rejected_event_count": int(rejected_event_count),
        "ticker_count": len(tickers),
        "provider_failures": failures,
        "validation_result": "passed",
        "required_successful_preview_runs": 5,
        "publication_enabled": False,
        "contents_write_permission_authorized": False,
        "schedule_enabled": False,
        "provider_network_calls_enabled": collection_mode == "live_primary_sources",
        "secrets_required": False,
        "external_writes_enabled": False,
        "published_to_repository": False,
        "artifact_retention_days": 3,
        "required_artifacts": [
            "news.jsonl",
            "collection_receipt.json",
            "news_manifest.preview.json",
            "run_report.json",
        ],
    }
    return receipt, manifest, report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build read-only public-news preview artifacts")
    parser.add_argument("--news", type=Path, required=True)
    parser.add_argument("--receipt-output", type=Path, required=True)
    parser.add_argument("--manifest-output", type=Path, required=True)
    parser.add_argument("--report-output", type=Path, required=True)
    parser.add_argument("--source-repository", default="poudlesuman32-star/ai-market-news")
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--generated-at", required=True)
    parser.add_argument("--collection-mode", choices=["fixture", "live_primary_sources"], default="fixture")
    parser.add_argument("--workflow-event", default="workflow_dispatch")
    parser.add_argument("--workflow-run-id", required=True)
    parser.add_argument("--workflow-run-attempt", required=True)
    parser.add_argument("--runtime-seconds", type=int, default=0)
    parser.add_argument("--sec-request-count", type=int, default=0)
    parser.add_argument("--company-request-count", type=int, default=0)
    parser.add_argument("--polygon-request-count", type=int, default=0)
    parser.add_argument("--finnhub-request-count", type=int, default=0)
    parser.add_argument("--raw-event-count", type=int)
    parser.add_argument("--normalized-event-count", type=int)
    parser.add_argument("--duplicate-count", type=int, default=0)
    parser.add_argument("--rejected-event-count", type=int, default=0)
    parser.add_argument("--provider-failures-json", default="[]")
    args = parser.parse_args(argv)

    try:
        failures = json.loads(args.provider_failures_json)
    except json.JSONDecodeError as exc:
        raise CollectorError(f"invalid provider failures JSON: {exc}") from exc
    require(isinstance(failures, list) and all(isinstance(item, str) for item in failures), "provider failures must be a JSON string list")

    receipt, manifest, report = build_preview_artifacts(
        news_path=args.news,
        source_repository=args.source_repository,
        source_commit=args.source_commit,
        run_id=args.run_id,
        generated_at_utc=args.generated_at,
        collection_mode=args.collection_mode,
        workflow_event=args.workflow_event,
        workflow_run_id=args.workflow_run_id,
        workflow_run_attempt=args.workflow_run_attempt,
        runtime_seconds=args.runtime_seconds,
        sec_request_count=args.sec_request_count,
        company_request_count=args.company_request_count,
        polygon_request_count=args.polygon_request_count,
        finnhub_request_count=args.finnhub_request_count,
        raw_event_count=args.raw_event_count,
        normalized_event_count=args.normalized_event_count,
        duplicate_count=args.duplicate_count,
        rejected_event_count=args.rejected_event_count,
        provider_failures=failures,
    )
    write_json(args.receipt_output, receipt)
    write_json(args.manifest_output, manifest)
    write_json(args.report_output, report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
