from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
import review_openfigi_mapping_artifact as mapping_review

CONTRACT_ID = "PPI-STABLE-INSTRUMENT-ID-ALLOCATION-PILOT-001-R1"
REVIEW_CONTRACT_ID = "PPI-OPENFIGI-MAPPING-ARTIFACT-REVIEW-001-R1"
SOURCE_CONTRACT_ID = "PPI-OPENFIGI-MAPPING-PILOT-001-R1"
REVIEW_WORKFLOW_NAME = "PPI OpenFIGI mapping artifact review"
EXPECTED_REPOSITORY = "poudlesuman32-star/ai-market-news"
REVIEW_PATHS = {"review.json", "review.md"}
SOURCE_PATHS = mapping_review.SUCCESS_PATHS
SUCCESS_PATHS = {"instrument-id-allocation-500.jsonl", "manifest.json", "receipt.json", "report.md"}
BLOCKED_PATHS = {"blocked.json", "report.md"}
EXPECTED_CANDIDATES = 500
EXPECTED_REQUESTS = 50
STATUSES = {"exact", "ambiguous", "unmatched"}
INSTRUMENT_ID = re.compile(r"^ppi-us-equity-[a-f0-9]{24}$")


class AllocationError(RuntimeError):
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
        raise AllocationError(f"Invalid JSON at {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise AllocationError(f"{path} must contain one object")
    return value


def files_under(root: Path) -> set[str]:
    try:
        return mapping_review.files_under(root)
    except mapping_review.ReviewError as exc:
        raise AllocationError(str(exc)) from exc


def valid_hex(value: object) -> bool:
    return isinstance(value, str) and bool(mapping_review.HEX64.fullmatch(value))


def validate_run(value: dict, run_id: str, attempt: str) -> dict:
    if not run_id.isdigit() or not attempt.isdigit():
        raise AllocationError("Run ID and attempt must be decimal integers")
    checks = {
        "id": value.get("id") == int(run_id),
        "attempt": value.get("run_attempt") == int(attempt),
        "name": value.get("name") == REVIEW_WORKFLOW_NAME,
        "repository": (value.get("repository") or {}).get("full_name") == EXPECTED_REPOSITORY,
        "main": value.get("head_branch") == "main",
        "completed": value.get("status") == "completed",
        "success": value.get("conclusion") == "success",
    }
    failed = [key for key, ok in checks.items() if not ok]
    if failed:
        raise AllocationError("Run identity failed: " + ", ".join(failed))
    return checks


def validate_review(review_root: Path, review_run_json: Path, review_run_id: str,
                    review_run_attempt: str) -> dict:
    if files_under(review_root) != REVIEW_PATHS:
        raise AllocationError("Review artifact paths are not exact")
    run_checks = validate_run(read_json(review_run_json), review_run_id, review_run_attempt)
    review = read_json(review_root / "review.json")
    core = {key: value for key, value in review.items() if key != "review_core_sha256"}
    authority = review.get("authority") or {}
    checks = {
        "review_contract": review.get("review_contract_id") == REVIEW_CONTRACT_ID,
        "source_contract": review.get("source_contract_id") == SOURCE_CONTRACT_ID,
        "repository": review.get("source_repository") == EXPECTED_REPOSITORY,
        "review_hash": review.get("review_core_sha256") == digest(canon(core)),
        "candidate_count_type": isinstance(review.get("candidate_count"), int),
        "request_count_type": isinstance(review.get("request_count"), int),
        "source_run_id_type": isinstance(review.get("source_run_id"), int),
        "source_run_attempt_type": isinstance(review.get("source_run_attempt"), int),
        "allocation_authority_false": authority.get("stable_instrument_id_allocation") is False,
        "no_private": authority.get("private_access") is False,
        "no_screening": authority.get("screening") is False,
        "no_deep": authority.get("deep_evidence_collection") is False,
        "no_registry": authority.get("registry_mutation") is False,
    }
    failed = [key for key, ok in checks.items() if not ok]
    if failed:
        raise AllocationError("Review receipt failed: " + ", ".join(failed))
    return {**review, "review_run_checks": run_checks}


def write_github_output(path: str | None, values: dict[str, object]) -> None:
    if not path:
        return
    with Path(path).open("a", encoding="utf-8") as handle:
        for key, value in values.items():
            text = str(value).lower() if isinstance(value, bool) else str(value)
            if "\n" in text or "\r" in text:
                raise AllocationError("GitHub output values must be single-line")
            handle.write(f"{key}={text}\n")


def write_blocked(root: Path, review: dict, reason: str) -> None:
    root.mkdir(parents=True, exist_ok=True)
    if any(root.iterdir()):
        raise AllocationError("Blocked output root must be empty")
    value = {
        "schema_version": "1.0.0", "contract_id": CONTRACT_ID, "status": "blocked",
        "reason": reason, "review_run_id": review.get("review_run_id"),
        "review_run_attempt": review.get("review_run_attempt"),
        "source_run_id": review.get("source_run_id"),
        "source_run_attempt": review.get("source_run_attempt"),
        "stable_instrument_ids_allocated": 0, "private_access": False,
        "screening": False, "deep_evidence_collection": False,
        "registry_mutation": False, "generated_at_utc": now(),
    }
    (root / "blocked.json").write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    (root / "report.md").write_text(
        "# PPI stable instrument ID allocation pilot\n\n"
        "**Status:** blocked before stable instrument ID allocation\n\n"
        f"Reason: {reason}\n"
    )
    if files_under(root) != BLOCKED_PATHS:
        raise AllocationError("Blocked output paths are not exact")


def write_failure(root: Path, stage: str, message: str, run_id: str, attempt: str) -> None:
    root.mkdir(parents=True, exist_ok=True)
    for child in list(root.iterdir()):
        if child.is_file():
            child.unlink()
    value = {
        "schema_version": "1.0.0", "contract_id": CONTRACT_ID, "status": "failed",
        "stage": stage, "error": message, "review_run_id": run_id,
        "review_run_attempt": attempt, "private_access": False, "screening": False,
        "deep_evidence_collection": False, "registry_mutation": False,
        "generated_at_utc": now(),
    }
    (root / "failure.json").write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    (root / "report.md").write_text(
        "# PPI stable instrument ID allocation pilot\n\n**Status:** failed closed\n\n"
        f"Stage: {stage}\n\nReason: {message}\n"
    )


def preflight(*, review_root: Path, review_run_json: Path, review_run_id: str,
              review_run_attempt: str, output_root: Path, github_output: str | None) -> dict:
    review = validate_review(review_root, review_run_json, review_run_id, review_run_attempt)
    counts = review.get("mapping_counts")
    passed = (
        review.get("gate_passed") is True
        and review.get("artifact_mode") == "success"
        and review.get("candidate_count") == EXPECTED_CANDIDATES
        and review.get("request_count") == EXPECTED_REQUESTS
        and isinstance(counts, dict) and set(counts) == STATUSES
        and all(isinstance(value, int) and value >= 0 for value in counts.values())
        and sum(counts.values()) == EXPECTED_CANDIDATES
        and valid_hex(review.get("mapping_snapshot_sha256"))
    )
    if not passed:
        write_blocked(
            output_root,
            {**review, "review_run_id": int(review_run_id), "review_run_attempt": int(review_run_attempt)},
            str(review.get("blocked_reason") or "OpenFIGI mapping artifact review gate did not pass"),
        )
    values = {
        "gate_passed": passed,
        "source_run_id": review.get("source_run_id", ""),
        "source_run_attempt": review.get("source_run_attempt", ""),
        "mapping_snapshot_sha256": review.get("mapping_snapshot_sha256", ""),
    }
    write_github_output(github_output, values)
    return values


def validate_mapping_artifact(source_root: Path, review: dict) -> list[dict]:
    if files_under(source_root) != SOURCE_PATHS:
        raise AllocationError("Mapping source artifact paths are not exact")
    expected_hashes = review.get("artifact_file_sha256")
    if not isinstance(expected_hashes, dict) or set(expected_hashes) != SOURCE_PATHS:
        raise AllocationError("Review receipt does not bind every mapping artifact path")
    actual_hashes = {path: digest((source_root / path).read_bytes()) for path in sorted(SOURCE_PATHS)}
    if actual_hashes != expected_hashes:
        raise AllocationError("Mapping artifact file hashes differ from the review receipt")
    snapshot = (source_root / "openfigi-mapping-500.jsonl").read_bytes()
    if digest(snapshot) != review.get("mapping_snapshot_sha256"):
        raise AllocationError("Mapping snapshot hash differs from the review receipt")
    lines = snapshot.splitlines()
    if not snapshot.endswith(b"\n") or len(lines) != EXPECTED_CANDIDATES or any(not line.strip() for line in lines):
        raise AllocationError("Mapping snapshot must contain exactly 500 canonical JSONL records")
    records = []
    for index, line in enumerate(lines, 1):
        try:
            records.append(mapping_review.validate_record(json.loads(line), index))
        except (json.JSONDecodeError, mapping_review.ReviewError) as exc:
            raise AllocationError(f"Mapping record {index} failed: {exc}") from exc
    candidate_ids = [record["candidate_id"] for record in records]
    if candidate_ids != sorted(candidate_ids) or len(set(candidate_ids)) != EXPECTED_CANDIDATES:
        raise AllocationError("Mapping records must be candidate-ID sorted and unique")
    counts = {state: sum(record["mapping_status"] == state for record in records) for state in STATUSES}
    if counts != review.get("mapping_counts"):
        raise AllocationError("Mapping classification counts differ from the review receipt")
    manifest = read_json(source_root / "manifest.json")
    receipt = read_json(source_root / "receipt.json")
    checks = {
        "manifest_contract": manifest.get("contract_id") == SOURCE_CONTRACT_ID,
        "manifest_snapshot": manifest.get("mapping_snapshot_sha256") == review.get("mapping_snapshot_sha256"),
        "manifest_source_snapshot": manifest.get("source_snapshot_sha256") == review.get("source_snapshot_sha256"),
        "manifest_core": manifest.get("manifest_core_sha256") == review.get("manifest_core_sha256"),
        "manifest_counts": manifest.get("mapping_counts") == review.get("mapping_counts"),
        "manifest_requests": manifest.get("request_count") == EXPECTED_REQUESTS,
        "receipt_contract": receipt.get("contract_id") == SOURCE_CONTRACT_ID,
        "receipt_snapshot": receipt.get("mapping_snapshot_sha256") == review.get("mapping_snapshot_sha256"),
        "receipt_run_id": str(receipt.get("run_id")) == str(review.get("source_run_id")),
        "receipt_run_attempt": str(receipt.get("run_attempt")) == str(review.get("source_run_attempt")),
        "receipt_requests": receipt.get("openfigi_requests_performed") == EXPECTED_REQUESTS,
        "no_api_key": receipt.get("api_key_used") is False,
        "raw_not_retained": receipt.get("raw_openfigi_responses_retained") is False,
        "no_private": receipt.get("private_access") is False,
        "no_screening": receipt.get("screening") is False,
        "no_deep": receipt.get("deep_evidence_collection") is False,
        "no_registry": receipt.get("registry_mutation") is False,
    }
    failed = [key for key, ok in checks.items() if not ok]
    if failed:
        raise AllocationError("Mapping source artifact failed: " + ", ".join(failed))
    return records


def identity_input(figi: str) -> bytes:
    return f"PPI-STABLE-INSTRUMENT-ID-V1|FIGI|{figi}".encode()


def stable_instrument_id(figi: str) -> str:
    return f"ppi-us-equity-{digest(identity_input(figi))[:24]}"


def allocate_records(records: list[dict]) -> list[dict]:
    if len(records) != EXPECTED_CANDIDATES:
        raise AllocationError("Exactly 500 reviewed mapping records are required")
    exact_figis = [record["matches"][0]["figi"] for record in records if record["mapping_status"] == "exact"]
    if len(exact_figis) != len(set(exact_figis)):
        raise AllocationError("Exact mapping records contain duplicate FIGIs; allocation is unsafe")
    outputs = []
    for record in records:
        base = {
            "candidate_id": record["candidate_id"], "cik": record["cik"],
            "ticker": record["ticker"], "exchange": record["exchange"],
            "source_row_sha256": record["source_row_sha256"],
            "mapping_status": record["mapping_status"],
            "mapping_record_sha256": digest(canon(record)),
        }
        if record["mapping_status"] == "exact":
            match = record["matches"][0]
            figi = match["figi"]
            output = {
                **base, "allocation_status": "allocated",
                "instrument_id": stable_instrument_id(figi), "identity_key_type": "FIGI",
                "identity_key_value": figi, "figi": figi,
                "composite_figi": match["composite_figi"],
                "share_class_figi": match["share_class_figi"],
                "identity_input_sha256": digest(identity_input(figi)),
            }
        else:
            output = {
                **base, "allocation_status": f"deferred_{record['mapping_status']}",
                "instrument_id": None, "identity_key_type": None, "identity_key_value": None,
                "figi": None, "composite_figi": None, "share_class_figi": None,
                "identity_input_sha256": None,
            }
        outputs.append(output)
    outputs.sort(key=lambda item: item["candidate_id"])
    ids = [item["instrument_id"] for item in outputs if item["instrument_id"] is not None]
    if len(ids) != len(set(ids)) or any(not INSTRUMENT_ID.fullmatch(value) for value in ids):
        raise AllocationError("Allocated instrument IDs are invalid or duplicated")
    return outputs


def write_outputs(root: Path, review: dict, records: list[dict], contract_path: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    if any(root.iterdir()):
        raise AllocationError("Allocation output root must be empty")
    snapshot = b"".join(canon(record) for record in records)
    counts = {
        "allocated": sum(record["allocation_status"] == "allocated" for record in records),
        "deferred_ambiguous": sum(record["allocation_status"] == "deferred_ambiguous" for record in records),
        "deferred_unmatched": sum(record["allocation_status"] == "deferred_unmatched" for record in records),
    }
    if sum(counts.values()) != EXPECTED_CANDIDATES:
        raise AllocationError("Allocation counts do not sum to 500")
    generated_at = now()
    core = {
        "schema_version": "1.0.0", "contract_id": CONTRACT_ID,
        "generated_at_utc": generated_at, "algorithm": "sha256_figi_namespace_v1",
        "instrument_id_prefix": "ppi-us-equity-", "review_run_id": review["review_run_id"],
        "review_run_attempt": review["review_run_attempt"], "source_run_id": review["source_run_id"],
        "source_run_attempt": review["source_run_attempt"],
        "source_snapshot_sha256": review["source_snapshot_sha256"],
        "mapping_snapshot_sha256": review["mapping_snapshot_sha256"],
        "candidate_count": len(records), "mapping_counts": review["mapping_counts"],
        "allocation_counts": counts, "allocation_snapshot_sha256": digest(snapshot),
        "ambiguous_and_unmatched_preserved": True, "network_requests_performed": 0,
    }
    manifest = {**core, "manifest_core_sha256": digest(canon(core))}
    receipt = {
        "schema_version": "1.0.0", "contract_id": CONTRACT_ID,
        "contract_sha256": digest(contract_path.read_bytes()),
        "repository": os.environ.get("GITHUB_REPOSITORY", "local"),
        "run_id": os.environ.get("GITHUB_RUN_ID"),
        "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        "event_name": os.environ.get("GITHUB_EVENT_NAME"), "head_sha": os.environ.get("GITHUB_SHA"),
        "generated_at_utc": generated_at,
        "allocation_snapshot_sha256": manifest["allocation_snapshot_sha256"],
        "mapping_snapshot_sha256": review["mapping_snapshot_sha256"],
        "manifest_core_sha256": manifest["manifest_core_sha256"],
        "stable_instrument_ids_allocated": counts["allocated"],
        "ambiguous_deferred": counts["deferred_ambiguous"],
        "unmatched_deferred": counts["deferred_unmatched"],
        "network_requests_performed": 0, "private_access": False, "screening": False,
        "deep_evidence_collection": False, "private_dispatch": False,
        "billing_budget_mutation": False, "registry_mutation": False,
        "production": False, "publication": False, "trading": False,
        "authorized_actions": ["stable_instrument_id_allocation_public_pilot"],
    }
    (root / "instrument-id-allocation-500.jsonl").write_bytes(snapshot)
    (root / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    (root / "receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    (root / "report.md").write_text(
        "# PPI stable instrument ID allocation pilot\n\n- Status: success\n"
        f"- Candidates: {len(records)}\n- Allocated: {counts['allocated']}\n"
        f"- Deferred ambiguous: {counts['deferred_ambiguous']}\n"
        f"- Deferred unmatched: {counts['deferred_unmatched']}\n"
        "- Identity algorithm: sha256_figi_namespace_v1\n- Network requests performed: 0\n"
        "- Private repository accessed: no\n- Screening or deep evidence performed: no\n"
        "- Registry mutated: no\n"
    )
    if files_under(root) != SUCCESS_PATHS:
        raise AllocationError("Success output paths are not exact")


def execute_allocation(*, review_root: Path, review_run_json: Path, review_run_id: str,
                       review_run_attempt: str, source_root: Path, output_root: Path,
                       contract_path: Path) -> dict:
    review = validate_review(review_root, review_run_json, review_run_id, review_run_attempt)
    if not (
        review.get("gate_passed") is True and review.get("artifact_mode") == "success"
        and review.get("candidate_count") == EXPECTED_CANDIDATES
        and review.get("request_count") == EXPECTED_REQUESTS
    ):
        raise AllocationError("Stable ID allocation requires an exact passed OpenFIGI review receipt")
    allocations = allocate_records(validate_mapping_artifact(source_root, review))
    write_outputs(
        output_root,
        {**review, "review_run_id": int(review_run_id), "review_run_attempt": int(review_run_attempt)},
        allocations, contract_path,
    )
    return {
        "candidate_count": len(allocations),
        "allocated_count": sum(item["allocation_status"] == "allocated" for item in allocations),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    pre = sub.add_parser("preflight")
    pre.add_argument("--review-root", type=Path, required=True)
    pre.add_argument("--review-run-json", type=Path, required=True)
    pre.add_argument("--review-run-id", required=True)
    pre.add_argument("--review-run-attempt", required=True)
    pre.add_argument("--output-root", type=Path, required=True)
    pre.add_argument("--github-output", default=os.environ.get("GITHUB_OUTPUT"))
    run = sub.add_parser("allocate")
    run.add_argument("--review-root", type=Path, required=True)
    run.add_argument("--review-run-json", type=Path, required=True)
    run.add_argument("--review-run-id", required=True)
    run.add_argument("--review-run-attempt", required=True)
    run.add_argument("--source-root", type=Path, required=True)
    run.add_argument("--output-root", type=Path, required=True)
    run.add_argument(
        "--contract", type=Path,
        default=Path("contracts/PPI-STABLE-INSTRUMENT-ID-ALLOCATION-PILOT-001-R1.json"),
    )
    args = parser.parse_args()
    try:
        if args.command == "preflight":
            preflight(
                review_root=args.review_root, review_run_json=args.review_run_json,
                review_run_id=args.review_run_id, review_run_attempt=args.review_run_attempt,
                output_root=args.output_root, github_output=args.github_output,
            )
        else:
            execute_allocation(
                review_root=args.review_root, review_run_json=args.review_run_json,
                review_run_id=args.review_run_id, review_run_attempt=args.review_run_attempt,
                source_root=args.source_root, output_root=args.output_root,
                contract_path=args.contract,
            )
        return 0
    except AllocationError as exc:
        write_failure(args.output_root, args.command, str(exc), args.review_run_id, args.review_run_attempt)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
