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
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    require(source_repository == "poudlesuman32-star/ai-market-news", "unexpected source repository")
    require(COMMIT_RE.fullmatch(source_commit) is not None, "source_commit must be a 40-character SHA")
    require(bool(run_id.strip()), "run_id is required")
    require(collection_mode == "fixture", "only fixture preview collection is authorized in this gate")

    records = load_news(news_path)
    providers = sorted({str(record["provider"]) for record in records})
    tickers = sorted({str(record["ticker"]) for record in records})
    event_ids = {str(record["event_id"]) for record in records}
    published = sorted(str(record["published_at_utc"]) for record in records)
    dataset_hash = sha256_file(news_path)

    receipt = {
        "schema_version": "1.0.0",
        "run_id": run_id,
        "collection_mode": collection_mode,
        "source_repository": source_repository,
        "source_commit": source_commit,
        "generated_at_utc": generated_at_utc,
        "collection_complete": True,
        "record_count": len(records),
        "event_count": len(event_ids),
        "provider_count": len(providers),
        "providers": providers,
        "tickers": tickers,
        "input_file": "news.jsonl",
        "dataset_sha256": dataset_hash,
        "synthetic_content_used": False,
        "source_content_modified": False,
        "private_content_excluded": True,
    }
    manifest = {
        "schema_version": "1.0.0",
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
        "earliest_publication_utc": published[0] if published else None,
        "latest_publication_utc": published[-1] if published else None,
        "synthetic_content_used": False,
        "source_content_modified": False,
        "private_content_excluded": True,
    }
    report = {
        "schema_version": "1.0.0",
        "stage": "PPI-R5",
        "phase": "manual_preview",
        "run_id": run_id,
        "success": True,
        "this_run_qualifies": True,
        "required_successful_preview_runs": 5,
        "publication_enabled": False,
        "contents_write_permission_authorized": False,
        "schedule_enabled": False,
        "provider_network_calls_enabled": False,
        "secrets_required": False,
        "external_writes_enabled": False,
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
    parser.add_argument("--collection-mode", default="fixture")
    args = parser.parse_args(argv)

    receipt, manifest, report = build_preview_artifacts(
        news_path=args.news,
        source_repository=args.source_repository,
        source_commit=args.source_commit,
        run_id=args.run_id,
        generated_at_utc=args.generated_at,
        collection_mode=args.collection_mode,
    )
    write_json(args.receipt_output, receipt)
    write_json(args.manifest_output, manifest)
    write_json(args.report_output, report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
