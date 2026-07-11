from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .build_preview_artifacts import build_preview_artifacts, write_json
from .collector_common import CollectorError, require

SUPPORTED_EVENTS = ("workflow_dispatch", "schedule")


def build_live_candidate_artifacts(
    *,
    news_path: Path,
    source_commit: str,
    run_id: str,
    generated_at_utc: str,
    workflow_event: str,
    workflow_run_id: str,
    workflow_run_attempt: str,
    runtime_seconds: int,
    sec_request_count: int,
    company_request_count: int,
    raw_event_count: int,
    normalized_event_count: int,
    duplicate_count: int,
    provider_failures: list[str],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    require(workflow_event in SUPPORTED_EVENTS, "unsupported live candidate workflow event")
    receipt, manifest, report = build_preview_artifacts(
        news_path=news_path,
        source_repository="poudlesuman32-star/ai-market-news",
        source_commit=source_commit,
        run_id=run_id,
        generated_at_utc=generated_at_utc,
        collection_mode="live_primary_sources",
        workflow_event="workflow_dispatch",
        workflow_run_id=workflow_run_id,
        workflow_run_attempt=workflow_run_attempt,
        runtime_seconds=runtime_seconds,
        sec_request_count=sec_request_count,
        company_request_count=company_request_count,
        raw_event_count=raw_event_count,
        normalized_event_count=normalized_event_count,
        duplicate_count=duplicate_count,
        provider_failures=provider_failures,
    )

    scheduled = workflow_event == "schedule"
    receipt.update(
        {
            "workflow_event": workflow_event,
            "candidate_only": True,
        }
    )
    manifest.update(
        {
            "candidate_only": True,
        }
    )
    report.update(
        {
            "phase": "automated_candidate_preview" if scheduled else "manual_candidate_preview",
            "workflow_event": workflow_event,
            "schedule_enabled": scheduled,
            "candidate_only": True,
            "artifact_retention_days": 30,
            "required_artifacts": [
                "news.jsonl",
                "collection_receipt.json",
                "news_manifest.preview.json",
                "run_report.json",
                "independent_validation.json",
            ],
            "publication_enabled": False,
            "contents_write_permission_authorized": False,
            "external_writes_enabled": False,
            "published_to_repository": False,
        }
    )
    return receipt, manifest, report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build read-only live preview candidate artifacts")
    parser.add_argument("--news", type=Path, required=True)
    parser.add_argument("--receipt-output", type=Path, required=True)
    parser.add_argument("--manifest-output", type=Path, required=True)
    parser.add_argument("--report-output", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--generated-at", required=True)
    parser.add_argument("--workflow-event", choices=SUPPORTED_EVENTS, required=True)
    parser.add_argument("--workflow-run-id", required=True)
    parser.add_argument("--workflow-run-attempt", required=True)
    parser.add_argument("--runtime-seconds", type=int, default=0)
    parser.add_argument("--sec-request-count", type=int, default=0)
    parser.add_argument("--company-request-count", type=int, default=0)
    parser.add_argument("--raw-event-count", type=int, required=True)
    parser.add_argument("--normalized-event-count", type=int, required=True)
    parser.add_argument("--duplicate-count", type=int, default=0)
    parser.add_argument("--provider-failures-json", default="[]")
    args = parser.parse_args(argv)

    try:
        failures = json.loads(args.provider_failures_json)
    except json.JSONDecodeError as exc:
        raise CollectorError(f"invalid provider failures JSON: {exc}") from exc
    require(isinstance(failures, list) and all(isinstance(item, str) for item in failures), "provider failures must be a string list")

    receipt, manifest, report = build_live_candidate_artifacts(
        news_path=args.news,
        source_commit=args.source_commit,
        run_id=args.run_id,
        generated_at_utc=args.generated_at,
        workflow_event=args.workflow_event,
        workflow_run_id=args.workflow_run_id,
        workflow_run_attempt=args.workflow_run_attempt,
        runtime_seconds=args.runtime_seconds,
        sec_request_count=args.sec_request_count,
        company_request_count=args.company_request_count,
        raw_event_count=args.raw_event_count,
        normalized_event_count=args.normalized_event_count,
        duplicate_count=args.duplicate_count,
        provider_failures=failures,
    )
    write_json(args.receipt_output, receipt)
    write_json(args.manifest_output, manifest)
    write_json(args.report_output, report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
