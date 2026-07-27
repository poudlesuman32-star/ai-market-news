from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

REVIEW_CONTRACT_ID = "PPI-OPENFIGI-MAPPING-ARTIFACT-REVIEW-001-R1"
SOURCE_CONTRACT_ID = "PPI-OPENFIGI-MAPPING-PILOT-001-R1"
SOURCE_WORKFLOW_NAME = "PPI OpenFIGI 500-candidate mapping pilot"
EXPECTED_REPOSITORY = "poudlesuman32-star/ai-market-news"
ENDPOINT = "https://api.openfigi.com/v3/mapping"
SUCCESS_PATHS = {"openfigi-mapping-500.jsonl", "manifest.json", "receipt.json", "report.md"}
BLOCKED_PATHS = {"blocked.json", "report.md"}
RECORD_FIELDS = {
    "candidate_id", "cik", "ticker", "exchange", "source_row_sha256",
    "mapping_status", "match_count", "matches", "request_sha256",
    "response_sha256", "reason",
}
MATCH_FIELDS = {
    "figi", "composite_figi", "share_class_figi", "ticker", "name",
    "exchange_code", "market_sector", "security_type", "security_type2",
    "security_description",
}
EXCHANGES = {"NYSE", "NASDAQ", "NYSE_AMERICAN"}
STATUSES = {"exact", "ambiguous", "unmatched"}
UNMATCHED_REASONS = {"no_identifier_found", "no_eligible_equity_match"}
HEX64 = re.compile(r"^[a-f0-9]{64}$")
CID = re.compile(r"^ppi-sec-seed-[a-f0-9]{24}$")
CIK = re.compile(r"^[0-9]{10}$")
TICKER = re.compile(r"^[A-Z0-9][A-Z0-9.\-]{0,14}$")
FIGI = re.compile(r"^[A-Z0-9]{12}$")
EXPECTED_CANDIDATES = 500
EXPECTED_REQUESTS = 50
JOBS_PER_REQUEST = 10


class ReviewError(RuntimeError):
    pass


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def canon(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode()


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReviewError(f"Invalid JSON at {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ReviewError(f"{path} must contain one object")
    return value


def files_under(root: Path) -> set[str]:
    if not root.is_dir():
        raise ReviewError(f"Artifact root is missing: {root}")
    paths = {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()}
    if any(path.startswith(".") or "/." in path for path in paths):
        raise ReviewError("Hidden artifact paths are forbidden")
    return paths


def validate_source_run(value: dict, run_id: str, attempt: str) -> dict:
    if not run_id.isdigit() or not attempt.isdigit():
        raise ReviewError("Source run ID and attempt must be decimal integers")
    checks = {
        "id": value.get("id") == int(run_id),
        "attempt": value.get("run_attempt") == int(attempt),
        "name": value.get("name") == SOURCE_WORKFLOW_NAME,
        "repository": (value.get("repository") or {}).get("full_name") == EXPECTED_REPOSITORY,
        "main": value.get("head_branch") == "main",
        "completed": value.get("status") == "completed",
        "success": value.get("conclusion") == "success",
    }
    failed = [key for key, ok in checks.items() if not ok]
    if failed:
        raise ReviewError("Source run identity failed: " + ", ".join(failed))
    return checks


def valid_hex(value: object) -> bool:
    return isinstance(value, str) and bool(HEX64.fullmatch(value))


def validate_blocked(root: Path) -> dict:
    value = read_json(root / "blocked.json")
    checks = {
        "contract": value.get("contract_id") == SOURCE_CONTRACT_ID,
        "status": value.get("status") == "blocked",
        "zero_requests": value.get("openfigi_requests_performed") == 0,
        "no_private": value.get("private_access") is False,
        "no_deep": value.get("deep_evidence_collection") is False,
        "no_registry": value.get("registry_mutation") is False,
    }
    failed = [key for key, ok in checks.items() if not ok]
    if failed:
        raise ReviewError("Blocked artifact failed: " + ", ".join(failed))
    return {
        "artifact_mode": "blocked",
        "gate_passed": False,
        "candidate_count": 0,
        "request_count": 0,
        "mapping_counts": {"exact": 0, "ambiguous": 0, "unmatched": 0},
        "blocked_reason": str(value.get("reason") or "unspecified"),
        "checks": checks,
    }


def validate_match(value: object, candidate_ticker: str, index: int, match_index: int) -> dict:
    if not isinstance(value, dict) or set(value) != MATCH_FIELDS:
        raise ReviewError(f"Record {index} match {match_index} fields differ from the frozen schema")
    required = {
        "figi": isinstance(value["figi"], str) and bool(FIGI.fullmatch(value["figi"])),
        "ticker": value["ticker"] == candidate_ticker,
        "market_sector": value["market_sector"] == "Equity",
    }
    for field in ("composite_figi", "share_class_figi"):
        required[field] = value[field] is None or (
            isinstance(value[field], str) and bool(FIGI.fullmatch(value[field]))
        )
    for field in ("name", "exchange_code", "security_type", "security_type2", "security_description"):
        required[field] = value[field] is None or isinstance(value[field], str)
    failed = [key for key, ok in required.items() if not ok]
    if failed:
        raise ReviewError(f"Record {index} match {match_index} failed: " + ", ".join(failed))
    return value


def validate_record(value: object, index: int) -> dict:
    if not isinstance(value, dict) or set(value) != RECORD_FIELDS:
        raise ReviewError(f"Record {index} fields differ from the frozen schema")
    checks = {
        "candidate_id": isinstance(value["candidate_id"], str) and bool(CID.fullmatch(value["candidate_id"])),
        "cik": isinstance(value["cik"], str) and bool(CIK.fullmatch(value["cik"])),
        "ticker": isinstance(value["ticker"], str) and bool(TICKER.fullmatch(value["ticker"])),
        "exchange": value["exchange"] in EXCHANGES,
        "source_row_hash": valid_hex(value["source_row_sha256"]),
        "status": value["mapping_status"] in STATUSES,
        "match_count_type": isinstance(value["match_count"], int) and not isinstance(value["match_count"], bool),
        "matches_type": isinstance(value["matches"], list),
        "request_hash": valid_hex(value["request_sha256"]),
        "response_hash": valid_hex(value["response_sha256"]),
        "reason_type": value["reason"] is None or isinstance(value["reason"], str),
    }
    failed = [key for key, ok in checks.items() if not ok]
    if failed:
        raise ReviewError(f"Record {index} failed: " + ", ".join(failed))
    matches = [
        validate_match(match, value["ticker"], index, match_index)
        for match_index, match in enumerate(value["matches"], 1)
    ]
    figis = [match["figi"] for match in matches]
    if figis != sorted(figis) or len(set(figis)) != len(figis):
        raise ReviewError(f"Record {index} matches must be FIGI-sorted and unique")
    if value["match_count"] != len(matches):
        raise ReviewError(f"Record {index} match_count differs from matches length")
    status = value["mapping_status"]
    if status == "exact":
        if len(matches) != 1 or value["reason"] is not None:
            raise ReviewError(f"Record {index} exact state is inconsistent")
    elif status == "ambiguous":
        if len(matches) <= 1 or value["reason"] != "multiple_eligible_figi_matches":
            raise ReviewError(f"Record {index} ambiguous state is inconsistent")
    elif matches or value["reason"] not in UNMATCHED_REASONS:
        raise ReviewError(f"Record {index} unmatched state is inconsistent")
    return value


def validate_success(root: Path, contract_path: Path, source_run_id: str, source_run_attempt: str) -> dict:
    snapshot = (root / "openfigi-mapping-500.jsonl").read_bytes()
    lines = snapshot.splitlines()
    if not snapshot.endswith(b"\n") or len(lines) != EXPECTED_CANDIDATES or any(not line.strip() for line in lines):
        raise ReviewError("Mapping snapshot must be canonical JSONL with exactly 500 non-empty lines")
    records = []
    for index, line in enumerate(lines, 1):
        try:
            records.append(validate_record(json.loads(line), index))
        except json.JSONDecodeError as exc:
            raise ReviewError(f"Record {index} is invalid JSON: {exc}") from exc
    candidate_ids = [record["candidate_id"] for record in records]
    source_keys = [(record["cik"], record["ticker"], record["exchange"]) for record in records]
    if candidate_ids != sorted(candidate_ids) or len(set(candidate_ids)) != EXPECTED_CANDIDATES:
        raise ReviewError("Mapping records must be candidate-ID sorted and unique")
    if len(set(source_keys)) != EXPECTED_CANDIDATES:
        raise ReviewError("Mapping records must have unique SEC source keys")
    counts = {state: sum(record["mapping_status"] == state for record in records) for state in ("exact", "ambiguous", "unmatched")}
    if sum(counts.values()) != EXPECTED_CANDIDATES:
        raise ReviewError("Mapping classification counts do not sum to 500")
    snapshot_hash = digest(snapshot)
    response_digest = digest(canon([record["response_sha256"] for record in records]))
    manifest = read_json(root / "manifest.json")
    manifest_core = {key: value for key, value in manifest.items() if key != "manifest_core_sha256"}
    checks = {
        "manifest_contract": manifest.get("contract_id") == SOURCE_CONTRACT_ID,
        "manifest_endpoint": manifest.get("endpoint") == ENDPOINT,
        "manifest_authentication": manifest.get("authentication_mode") == "unauthenticated_free_tier",
        "manifest_no_api_key": manifest.get("api_key_used") is False,
        "manifest_candidate_count": manifest.get("candidate_count") == EXPECTED_CANDIDATES,
        "manifest_jobs_per_request": manifest.get("jobs_per_request") == JOBS_PER_REQUEST,
        "manifest_request_count": manifest.get("request_count") == EXPECTED_REQUESTS,
        "manifest_mapping_counts": manifest.get("mapping_counts") == counts,
        "manifest_snapshot_hash": manifest.get("mapping_snapshot_sha256") == snapshot_hash,
        "manifest_source_snapshot_hash": valid_hex(manifest.get("source_snapshot_sha256")),
        "manifest_response_digest": manifest.get("normalized_response_digest_sha256") == response_digest,
        "manifest_raw_not_retained": manifest.get("raw_openfigi_responses_retained") is False,
        "manifest_hash": manifest.get("manifest_core_sha256") == digest(canon(manifest_core)),
    }
    receipt = read_json(root / "receipt.json")
    checks.update({
        "receipt_contract": receipt.get("contract_id") == SOURCE_CONTRACT_ID,
        "receipt_contract_hash": receipt.get("contract_sha256") == digest(contract_path.read_bytes()),
        "receipt_repository": receipt.get("repository") == EXPECTED_REPOSITORY,
        "receipt_run_id": str(receipt.get("run_id")) == source_run_id,
        "receipt_run_attempt": str(receipt.get("run_attempt")) == source_run_attempt,
        "receipt_mapping_snapshot": receipt.get("mapping_snapshot_sha256") == snapshot_hash,
        "receipt_manifest": receipt.get("manifest_core_sha256") == manifest.get("manifest_core_sha256"),
        "receipt_source_snapshot": receipt.get("source_snapshot_sha256") == manifest.get("source_snapshot_sha256"),
        "receipt_requests": receipt.get("openfigi_requests_performed") == EXPECTED_REQUESTS,
        "receipt_no_api_key": receipt.get("api_key_used") is False,
        "receipt_raw_not_retained": receipt.get("raw_openfigi_responses_retained") is False,
        "receipt_no_private": receipt.get("private_access") is False,
        "receipt_no_screening": receipt.get("screening") is False,
        "receipt_no_deep": receipt.get("deep_evidence_collection") is False,
        "receipt_no_dispatch": receipt.get("private_dispatch") is False,
        "receipt_no_billing": receipt.get("billing_budget_mutation") is False,
        "receipt_no_registry": receipt.get("registry_mutation") is False,
        "receipt_no_production": receipt.get("production") is False,
        "receipt_no_publication": receipt.get("publication") is False,
        "receipt_no_trading": receipt.get("trading") is False,
        "receipt_exact_authority": receipt.get("authorized_actions") == ["openfigi_mapping_public_pilot"],
    })
    report = (root / "report.md").read_text(encoding="utf-8")
    checks.update({
        "report_success": "- Status: success" in report,
        "report_candidates": "- Candidates: 500" in report,
        "report_requests": "- Requests: 50" in report,
        "report_exact": f"- Exact: {counts['exact']}" in report,
        "report_ambiguous": f"- Ambiguous: {counts['ambiguous']}" in report,
        "report_unmatched": f"- Unmatched: {counts['unmatched']}" in report,
    })
    failed = [key for key, ok in checks.items() if not ok]
    if failed:
        raise ReviewError("Success artifact failed: " + ", ".join(failed))
    return {
        "artifact_mode": "success",
        "gate_passed": True,
        "candidate_count": EXPECTED_CANDIDATES,
        "request_count": EXPECTED_REQUESTS,
        "mapping_counts": counts,
        "source_snapshot_sha256": manifest["source_snapshot_sha256"],
        "mapping_snapshot_sha256": snapshot_hash,
        "manifest_core_sha256": manifest["manifest_core_sha256"],
        "normalized_response_digest_sha256": response_digest,
        "artifact_file_sha256": {path: digest((root / path).read_bytes()) for path in sorted(SUCCESS_PATHS)},
        "checks": checks,
    }


def review_artifact(*, artifact_root: Path, source_run_json: Path, source_run_id: str, source_run_attempt: str, contract_path: Path) -> dict:
    source_checks = validate_source_run(read_json(source_run_json), source_run_id, source_run_attempt)
    paths = files_under(artifact_root)
    if paths == BLOCKED_PATHS:
        result = validate_blocked(artifact_root)
    elif paths == SUCCESS_PATHS:
        result = validate_success(artifact_root, contract_path, source_run_id, source_run_attempt)
    else:
        raise ReviewError("Artifact paths are not exact: " + ", ".join(sorted(paths)))
    return {
        "schema_version": "1.0.0",
        "review_contract_id": REVIEW_CONTRACT_ID,
        "source_contract_id": SOURCE_CONTRACT_ID,
        "source_repository": EXPECTED_REPOSITORY,
        "source_run_id": int(source_run_id),
        "source_run_attempt": int(source_run_attempt),
        "reviewed_at_utc": now(),
        "source_run_checks": source_checks,
        **result,
        "authority": {
            "stable_instrument_id_allocation": False,
            "screening": False,
            "deep_evidence_collection": False,
            "private_access": False,
            "private_dispatch": False,
            "billing_budget_mutation": False,
            "registry_mutation": False,
            "production": False,
            "publication": False,
            "trading": False,
        },
    }


def write_review(root: Path, value: dict) -> None:
    root.mkdir(parents=True, exist_ok=True)
    if any(root.iterdir()):
        raise ReviewError("Review output root must be empty")
    output = {**value, "review_core_sha256": digest(canon(value))}
    (root / "review.json").write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    status = "passed" if value.get("gate_passed") else "blocked"
    counts = value.get("mapping_counts") or {}
    lines = [
        "# PPI OpenFIGI mapping artifact review", "", f"- Status: {status}",
        f"- Source run: {value.get('source_run_id')} attempt {value.get('source_run_attempt')}",
        f"- Artifact mode: {value.get('artifact_mode')}",
        f"- Gate passed: {'yes' if value.get('gate_passed') else 'no'}",
        f"- Candidate count: {value.get('candidate_count', 0)}",
        f"- Request count: {value.get('request_count', 0)}",
        f"- Exact: {counts.get('exact', 0)}", f"- Ambiguous: {counts.get('ambiguous', 0)}",
        f"- Unmatched: {counts.get('unmatched', 0)}", "- Stable instrument IDs allocated: no",
        "- Private repository accessed: no", "- Screening or deep evidence performed: no",
    ]
    if value.get("blocked_reason"):
        lines.append(f"- Blocked reason: {value['blocked_reason']}")
    if value.get("mapping_snapshot_sha256"):
        lines.append(f"- Mapping snapshot SHA-256: `{value['mapping_snapshot_sha256']}`")
    (root / "review.md").write_text("\n".join(lines) + "\n")
    if files_under(root) != {"review.json", "review.md"}:
        raise ReviewError("Review output paths are not exact")


def write_failure(root: Path, message: str, run_id: str, attempt: str) -> None:
    root.mkdir(parents=True, exist_ok=True)
    for child in list(root.iterdir()):
        if child.is_file():
            child.unlink()
    value = {
        "schema_version": "1.0.0", "review_contract_id": REVIEW_CONTRACT_ID,
        "status": "failed", "gate_passed": False, "source_run_id": run_id,
        "source_run_attempt": attempt, "reviewed_at_utc": now(), "error": message,
        "authority": {
            "stable_instrument_id_allocation": False, "screening": False,
            "deep_evidence_collection": False, "private_access": False,
            "private_dispatch": False, "billing_budget_mutation": False,
            "registry_mutation": False, "production": False,
            "publication": False, "trading": False,
        },
    }
    (root / "review.json").write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    (root / "review.md").write_text(
        "# PPI OpenFIGI mapping artifact review\n\n**Status:** failed closed\n\n" + f"Reason: {message}\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--source-run-json", type=Path, required=True)
    parser.add_argument("--source-run-id", required=True)
    parser.add_argument("--source-run-attempt", required=True)
    parser.add_argument("--contract", type=Path, default=Path("contracts/PPI-OPENFIGI-MAPPING-PILOT-001-R1.json"))
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    try:
        value = review_artifact(
            artifact_root=args.artifact_root, source_run_json=args.source_run_json,
            source_run_id=args.source_run_id, source_run_attempt=args.source_run_attempt,
            contract_path=args.contract,
        )
        write_review(args.output_root, value)
        return 0
    except ReviewError as exc:
        write_failure(args.output_root, str(exc), args.source_run_id, args.source_run_attempt)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
