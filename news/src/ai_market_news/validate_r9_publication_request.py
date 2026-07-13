from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from .collector_common import CollectorError, require

EXPECTED_PUBLIC_REPOSITORY = "poudlesuman32-star/ai-market-news"
EXPECTED_WORKFLOW_NAME = "PPI public news live primary-source preview"
EXPECTED_CONTRACT_ID = "PPI-R9-AUTONOMY-002"
EXPECTED_ENVIRONMENT = "ppi-r9-manual-approval"
SHA40_RE = re.compile(r"^[0-9a-f]{40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
ACTOR_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$")


def read_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CollectorError(f"cannot read valid JSON object: {path}") from exc
    require(isinstance(value, dict), f"expected JSON object: {path}")
    return value


def parse_utc(value: str, *, field: str) -> dt.datetime:
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CollectorError(f"{field} must be ISO-8601") from exc
    require(parsed.tzinfo is not None, f"{field} must include a timezone")
    return parsed.astimezone(dt.timezone.utc)


def canonical_utc(value: dt.datetime) -> str:
    return value.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def request_digest(value: dict[str, Any]) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def validate_publication_request(
    *,
    source_run_path: Path,
    news_path: Path,
    receipt_path: Path,
    manifest_path: Path,
    report_path: Path,
    source_run_id: str,
    source_run_attempt: str,
    candidate_sha256: str,
    contract_sha256: str,
    authorization_issued_at_utc: str,
    authorization_expires_at_utc: str,
    requested_by: str,
    now_utc: str | None = None,
) -> dict[str, Any]:
    require(source_run_id.isdigit() and int(source_run_id) > 0, "source run ID must be positive")
    require(source_run_attempt.isdigit() and int(source_run_attempt) > 0, "source run attempt must be positive")
    require(SHA256_RE.fullmatch(candidate_sha256) is not None, "candidate SHA-256 must be lowercase hexadecimal")
    require(SHA256_RE.fullmatch(contract_sha256) is not None, "contract SHA-256 must be lowercase hexadecimal")
    require(ACTOR_RE.fullmatch(requested_by) is not None, "requested_by is not a valid GitHub actor")
    require(news_path.is_file() and news_path.stat().st_size > 0, "news candidate is empty or missing")

    source_run = read_object(source_run_path)
    receipt = read_object(receipt_path)
    manifest = read_object(manifest_path)
    report = read_object(report_path)

    require(str(source_run.get("id")) == source_run_id, "source run ID mismatch")
    require(str(source_run.get("run_attempt")) == source_run_attempt, "source run attempt mismatch")
    require(source_run.get("event") == "workflow_dispatch", "source run must be manually dispatched")
    require(source_run.get("status") in {None, "completed"}, "source run is not completed")
    require(source_run.get("conclusion") == "success", "source run did not succeed")
    require(source_run.get("head_branch") == "main", "source run branch mismatch")
    head_repository = source_run.get("head_repository")
    require(isinstance(head_repository, dict), "source run repository metadata missing")
    require(head_repository.get("full_name") == EXPECTED_PUBLIC_REPOSITORY, "source run repository mismatch")
    require(source_run.get("name") == EXPECTED_WORKFLOW_NAME, "source workflow name mismatch")
    head_sha = str(source_run.get("head_sha", ""))
    require(SHA40_RE.fullmatch(head_sha) is not None, "source run head SHA is invalid")

    completed_value = source_run.get("updated_at") or source_run.get("run_started_at") or source_run.get("created_at")
    require(isinstance(completed_value, str) and completed_value, "source run completion time missing")
    completed = parse_utc(completed_value, field="source run completion time")
    issued = parse_utc(authorization_issued_at_utc, field="authorization issue time")
    expires = parse_utc(authorization_expires_at_utc, field="authorization expiry time")
    now = parse_utc(now_utc, field="validation time") if now_utc else dt.datetime.now(dt.timezone.utc)
    require(completed <= issued, "authorization cannot predate source run completion")
    require(issued <= now <= expires, "authorization is not currently valid")
    require(expires > issued, "authorization expiry must follow issue time")
    require(expires - completed <= dt.timedelta(hours=24), "authorization window exceeds 24 hours from source completion")

    digest = sha256_file(news_path)
    require(digest == candidate_sha256, "candidate digest mismatch")

    require(receipt.get("source_repository") == EXPECTED_PUBLIC_REPOSITORY, "receipt repository mismatch")
    require(receipt.get("source_commit") == head_sha, "receipt source commit mismatch")
    require(receipt.get("collection_mode") == "live_primary_sources", "receipt is not live primary-source evidence")
    require(receipt.get("collection_complete") is True, "receipt is incomplete")
    require(receipt.get("dataset_sha256") == digest, "receipt dataset digest mismatch")
    require(receipt.get("provider_failures") == [], "provider failures block publication")
    require(receipt.get("synthetic_content_used") is False, "synthetic content blocks publication")
    require(receipt.get("source_content_modified") is False, "modified source content blocks publication")
    require(receipt.get("private_content_excluded") is True, "private-content exclusion is not confirmed")
    provider_counts = receipt.get("provider_counts")
    require(isinstance(provider_counts, dict), "receipt provider counts missing")
    require(int(provider_counts.get("sec_edgar", 0)) > 0, "accepted SEC evidence is missing")
    require(int(provider_counts.get("official_company_source", 0)) > 0, "accepted official-company evidence is missing")

    require(manifest.get("publication_status") == "preview_only", "manifest is not preview-only")
    require(manifest.get("source_repository") == EXPECTED_PUBLIC_REPOSITORY, "manifest repository mismatch")
    require(manifest.get("source_commit") == head_sha, "manifest source commit mismatch")
    require(manifest.get("file_sha256") == digest, "manifest candidate digest mismatch")
    require(manifest.get("synthetic_content_used") is False, "manifest reports synthetic content")
    require(manifest.get("source_content_modified") is False, "manifest reports modified source content")
    require(manifest.get("private_content_excluded") is True, "manifest does not confirm private-content exclusion")

    require(report.get("workflow_event") == "workflow_dispatch", "run report is not from manual dispatch")
    require(str(report.get("workflow_run_id")) == source_run_id, "run report ID mismatch")
    require(str(report.get("workflow_run_attempt")) == source_run_attempt, "run report attempt mismatch")
    require(report.get("source_commit") == head_sha, "run report source commit mismatch")
    require(report.get("this_run_qualifies") is True, "run report does not qualify")
    require(report.get("qualification_exclusion_reasons") == [], "run report has exclusion reasons")
    require(report.get("provider_failures") == [], "run report has provider failures")
    require(report.get("schedule_enabled") is False, "scheduled preview cannot publish")
    require(report.get("published_to_repository") is False, "candidate was already published")
    require(report.get("external_writes_enabled") is False, "candidate run enabled external writes")
    require(report.get("contents_write_permission_authorized") is False, "candidate run had write authority")
    require(receipt.get("run_id") == report.get("run_id"), "receipt and report run identity mismatch")

    base_evidence = {
        "schema_version": "1.0.0",
        "authorization_type": "protected_environment_request",
        "environment": EXPECTED_ENVIRONMENT,
        "environment_gate_passed": False,
        "requested_by": requested_by,
        "source_repository": EXPECTED_PUBLIC_REPOSITORY,
        "source_workflow_name": EXPECTED_WORKFLOW_NAME,
        "source_workflow_event": "workflow_dispatch",
        "source_workflow_run_id": source_run_id,
        "source_workflow_run_attempt": source_run_attempt,
        "source_head_sha": head_sha,
        "candidate_sha256": digest,
        "contract_id": EXPECTED_CONTRACT_ID,
        "contract_sha256": contract_sha256,
        "source_completed_at_utc": canonical_utc(completed),
        "issued_at_utc": canonical_utc(issued),
        "expires_at_utc": canonical_utc(expires),
        "validated_at_utc": canonical_utc(now),
        "validation_result": "passed",
    }
    evidence = dict(base_evidence)
    evidence["authorization_request_sha256"] = request_digest(base_evidence)
    return evidence


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate one exact manual R9 public publication request")
    parser.add_argument("--source-run", type=Path, required=True)
    parser.add_argument("--news", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--source-run-id", required=True)
    parser.add_argument("--source-run-attempt", required=True)
    parser.add_argument("--candidate-sha256", required=True)
    parser.add_argument("--contract-sha256", required=True)
    parser.add_argument("--authorization-issued-at-utc", required=True)
    parser.add_argument("--authorization-expires-at-utc", required=True)
    parser.add_argument("--requested-by", required=True)
    parser.add_argument("--now-utc")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    evidence = validate_publication_request(
        source_run_path=args.source_run,
        news_path=args.news,
        receipt_path=args.receipt,
        manifest_path=args.manifest,
        report_path=args.report,
        source_run_id=args.source_run_id,
        source_run_attempt=args.source_run_attempt,
        candidate_sha256=args.candidate_sha256,
        contract_sha256=args.contract_sha256,
        authorization_issued_at_utc=args.authorization_issued_at_utc,
        authorization_expires_at_utc=args.authorization_expires_at_utc,
        requested_by=args.requested_by,
        now_utc=args.now_utc,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
