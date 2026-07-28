from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
import allocate_stable_instrument_ids as allocator

REVIEW_CONTRACT_ID = "PPI-STABLE-INSTRUMENT-ID-ALLOCATION-ARTIFACT-REVIEW-001-R1"
SOURCE_CONTRACT_ID = allocator.CONTRACT_ID
SOURCE_WORKFLOW_NAME = "PPI stable instrument ID allocation pilot"
EXPECTED_REPOSITORY = "poudlesuman32-star/ai-market-news"
SUCCESS_PATHS = allocator.SUCCESS_PATHS
BLOCKED_PATHS = allocator.BLOCKED_PATHS
EXPECTED_CANDIDATES = 500
ALLOCATION_STATUSES = {"allocated", "deferred_ambiguous", "deferred_unmatched"}
RECORD_FIELDS = {
    "candidate_id", "cik", "ticker", "exchange", "source_row_sha256",
    "mapping_status", "mapping_record_sha256", "allocation_status",
    "instrument_id", "identity_key_type", "identity_key_value",
    "figi", "composite_figi", "share_class_figi", "identity_input_sha256",
}


class ReviewError(RuntimeError):
    pass


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def canon(value: object) -> bytes:
    return allocator.canon(value)


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
    try:
        return allocator.files_under(root)
    except allocator.AllocationError as exc:
        raise ReviewError(str(exc)) from exc


def valid_hex(value: object) -> bool:
    return isinstance(value, str) and bool(allocator.mapping_review.HEX64.fullmatch(value))


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


def validate_blocked(root: Path) -> dict:
    value = read_json(root / "blocked.json")
    checks = {
        "contract": value.get("contract_id") == SOURCE_CONTRACT_ID,
        "status": value.get("status") == "blocked",
        "zero_ids": value.get("stable_instrument_ids_allocated") == 0,
        "no_private": value.get("private_access") is False,
        "no_screening": value.get("screening") is False,
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
        "allocation_counts": {
            "allocated": 0,
            "deferred_ambiguous": 0,
            "deferred_unmatched": 0,
        },
        "blocked_reason": str(value.get("reason") or "unspecified"),
        "checks": checks,
    }


def optional_figi(value: object) -> bool:
    return value is None or (
        isinstance(value, str) and bool(allocator.mapping_review.FIGI.fullmatch(value))
    )


def validate_record(value: object, index: int) -> dict:
    if not isinstance(value, dict) or set(value) != RECORD_FIELDS:
        raise ReviewError(f"Record {index} fields differ from the frozen schema")
    checks = {
        "candidate_id": isinstance(value["candidate_id"], str)
        and bool(allocator.mapping_review.CID.fullmatch(value["candidate_id"])),
        "cik": isinstance(value["cik"], str)
        and bool(allocator.mapping_review.CIK.fullmatch(value["cik"])),
        "ticker": isinstance(value["ticker"], str)
        and bool(allocator.mapping_review.TICKER.fullmatch(value["ticker"])),
        "exchange": value["exchange"] in allocator.mapping_review.EXCHANGES,
        "source_row_hash": valid_hex(value["source_row_sha256"]),
        "mapping_status": value["mapping_status"] in allocator.STATUSES,
        "mapping_record_hash": valid_hex(value["mapping_record_sha256"]),
        "allocation_status": value["allocation_status"] in ALLOCATION_STATUSES,
    }
    failed = [key for key, ok in checks.items() if not ok]
    if failed:
        raise ReviewError(f"Record {index} failed: " + ", ".join(failed))

    status = value["allocation_status"]
    if status == "allocated":
        figi = value["figi"]
        allocated_checks = {
            "mapping_exact": value["mapping_status"] == "exact",
            "figi": isinstance(figi, str)
            and bool(allocator.mapping_review.FIGI.fullmatch(figi)),
            "instrument_id": isinstance(value["instrument_id"], str)
            and bool(allocator.INSTRUMENT_ID.fullmatch(value["instrument_id"])),
            "identity_type": value["identity_key_type"] == "FIGI",
            "identity_value": value["identity_key_value"] == figi,
            "composite_figi": optional_figi(value["composite_figi"]),
            "share_class_figi": optional_figi(value["share_class_figi"]),
            "identity_hash": value["identity_input_sha256"]
            == digest(allocator.identity_input(figi))
            if isinstance(figi, str)
            else False,
            "derived_id": value["instrument_id"] == allocator.stable_instrument_id(figi)
            if isinstance(figi, str)
            else False,
        }
        failed = [key for key, ok in allocated_checks.items() if not ok]
        if failed:
            raise ReviewError(
                f"Record {index} allocated state failed: " + ", ".join(failed)
            )
    else:
        expected_mapping = status.removeprefix("deferred_")
        deferred_checks = {
            "mapping_status": value["mapping_status"] == expected_mapping,
            "instrument_id": value["instrument_id"] is None,
            "identity_type": value["identity_key_type"] is None,
            "identity_value": value["identity_key_value"] is None,
            "figi": value["figi"] is None,
            "composite_figi": value["composite_figi"] is None,
            "share_class_figi": value["share_class_figi"] is None,
            "identity_hash": value["identity_input_sha256"] is None,
        }
        failed = [key for key, ok in deferred_checks.items() if not ok]
        if failed:
            raise ReviewError(
                f"Record {index} deferred state failed: " + ", ".join(failed)
            )
    return value


def validate_success(root: Path, contract_path: Path, run_id: str, attempt: str) -> dict:
    snapshot = (root / "instrument-id-allocation-500.jsonl").read_bytes()
    lines = snapshot.splitlines()
    if (
        not snapshot.endswith(b"\n")
        or len(lines) != EXPECTED_CANDIDATES
        or any(not line.strip() for line in lines)
    ):
        raise ReviewError(
            "Allocation snapshot must contain exactly 500 canonical JSONL records"
        )
    records = []
    for index, line in enumerate(lines, 1):
        try:
            records.append(validate_record(json.loads(line), index))
        except json.JSONDecodeError as exc:
            raise ReviewError(f"Record {index} is invalid JSON: {exc}") from exc
    candidate_ids = [record["candidate_id"] for record in records]
    source_keys = [
        (record["cik"], record["ticker"], record["exchange"]) for record in records
    ]
    instrument_ids = [
        record["instrument_id"]
        for record in records
        if record["instrument_id"] is not None
    ]
    if candidate_ids != sorted(candidate_ids) or len(set(candidate_ids)) != EXPECTED_CANDIDATES:
        raise ReviewError("Allocation records must be candidate-ID sorted and unique")
    if len(set(source_keys)) != EXPECTED_CANDIDATES:
        raise ReviewError("Allocation records must have unique SEC source keys")
    if len(instrument_ids) != len(set(instrument_ids)):
        raise ReviewError("Allocated instrument IDs must be unique")

    counts = {
        state: sum(record["allocation_status"] == state for record in records)
        for state in ALLOCATION_STATUSES
    }
    mapping_counts = {
        state: sum(record["mapping_status"] == state for record in records)
        for state in allocator.STATUSES
    }
    if sum(counts.values()) != EXPECTED_CANDIDATES:
        raise ReviewError("Allocation counts do not sum to 500")
    if counts["allocated"] != mapping_counts["exact"]:
        raise ReviewError("Allocated count differs from exact mapping count")
    if counts["deferred_ambiguous"] != mapping_counts["ambiguous"]:
        raise ReviewError("Deferred ambiguous count differs from mapping count")
    if counts["deferred_unmatched"] != mapping_counts["unmatched"]:
        raise ReviewError("Deferred unmatched count differs from mapping count")

    snapshot_hash = digest(snapshot)
    manifest = read_json(root / "manifest.json")
    core = {key: value for key, value in manifest.items() if key != "manifest_core_sha256"}
    checks = {
        "manifest_contract": manifest.get("contract_id") == SOURCE_CONTRACT_ID,
        "manifest_algorithm": manifest.get("algorithm") == "sha256_figi_namespace_v1",
        "manifest_prefix": manifest.get("instrument_id_prefix") == "ppi-us-equity-",
        "manifest_candidate_count": manifest.get("candidate_count") == EXPECTED_CANDIDATES,
        "manifest_mapping_counts": manifest.get("mapping_counts") == mapping_counts,
        "manifest_allocation_counts": manifest.get("allocation_counts") == counts,
        "manifest_snapshot": manifest.get("allocation_snapshot_sha256") == snapshot_hash,
        "manifest_source_snapshot": valid_hex(manifest.get("source_snapshot_sha256")),
        "manifest_mapping_snapshot": valid_hex(manifest.get("mapping_snapshot_sha256")),
        "manifest_preserved": manifest.get("ambiguous_and_unmatched_preserved") is True,
        "manifest_zero_network": manifest.get("network_requests_performed") == 0,
        "manifest_hash": manifest.get("manifest_core_sha256") == digest(canon(core)),
    }
    receipt = read_json(root / "receipt.json")
    checks.update(
        {
            "receipt_contract": receipt.get("contract_id") == SOURCE_CONTRACT_ID,
            "receipt_contract_hash": receipt.get("contract_sha256")
            == digest(contract_path.read_bytes()),
            "receipt_repository": receipt.get("repository") == EXPECTED_REPOSITORY,
            "receipt_run_id": str(receipt.get("run_id")) == run_id,
            "receipt_run_attempt": str(receipt.get("run_attempt")) == attempt,
            "receipt_snapshot": receipt.get("allocation_snapshot_sha256") == snapshot_hash,
            "receipt_mapping_snapshot": receipt.get("mapping_snapshot_sha256")
            == manifest.get("mapping_snapshot_sha256"),
            "receipt_manifest": receipt.get("manifest_core_sha256")
            == manifest.get("manifest_core_sha256"),
            "receipt_allocated": receipt.get("stable_instrument_ids_allocated")
            == counts["allocated"],
            "receipt_ambiguous": receipt.get("ambiguous_deferred")
            == counts["deferred_ambiguous"],
            "receipt_unmatched": receipt.get("unmatched_deferred")
            == counts["deferred_unmatched"],
            "receipt_zero_network": receipt.get("network_requests_performed") == 0,
            "receipt_no_private": receipt.get("private_access") is False,
            "receipt_no_screening": receipt.get("screening") is False,
            "receipt_no_deep": receipt.get("deep_evidence_collection") is False,
            "receipt_no_dispatch": receipt.get("private_dispatch") is False,
            "receipt_no_billing": receipt.get("billing_budget_mutation") is False,
            "receipt_no_registry": receipt.get("registry_mutation") is False,
            "receipt_no_production": receipt.get("production") is False,
            "receipt_no_publication": receipt.get("publication") is False,
            "receipt_no_trading": receipt.get("trading") is False,
            "receipt_exact_authority": receipt.get("authorized_actions")
            == ["stable_instrument_id_allocation_public_pilot"],
        }
    )
    report = (root / "report.md").read_text(encoding="utf-8")
    checks.update(
        {
            "report_success": "- Status: success" in report,
            "report_candidates": "- Candidates: 500" in report,
            "report_allocated": f"- Allocated: {counts['allocated']}" in report,
            "report_ambiguous": f"- Deferred ambiguous: {counts['deferred_ambiguous']}"
            in report,
            "report_unmatched": f"- Deferred unmatched: {counts['deferred_unmatched']}"
            in report,
        }
    )
    failed = [key for key, ok in checks.items() if not ok]
    if failed:
        raise ReviewError("Success artifact failed: " + ", ".join(failed))
    return {
        "artifact_mode": "success",
        "gate_passed": True,
        "candidate_count": EXPECTED_CANDIDATES,
        "allocation_counts": counts,
        "mapping_counts": mapping_counts,
        "source_snapshot_sha256": manifest["source_snapshot_sha256"],
        "mapping_snapshot_sha256": manifest["mapping_snapshot_sha256"],
        "allocation_snapshot_sha256": snapshot_hash,
        "manifest_core_sha256": manifest["manifest_core_sha256"],
        "artifact_file_sha256": {
            path: digest((root / path).read_bytes()) for path in sorted(SUCCESS_PATHS)
        },
        "checks": checks,
    }


def review_artifact(
    *,
    artifact_root: Path,
    source_run_json: Path,
    source_run_id: str,
    source_run_attempt: str,
    contract_path: Path,
) -> dict:
    source_checks = validate_source_run(
        read_json(source_run_json), source_run_id, source_run_attempt
    )
    paths = files_under(artifact_root)
    if paths == BLOCKED_PATHS:
        result = validate_blocked(artifact_root)
    elif paths == SUCCESS_PATHS:
        result = validate_success(
            artifact_root, contract_path, source_run_id, source_run_attempt
        )
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
            "universe_snapshot_assembly": False,
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
    (root / "review.json").write_text(
        json.dumps(output, indent=2, sort_keys=True) + "\n"
    )
    counts = value.get("allocation_counts") or {}
    status = "passed" if value.get("gate_passed") else "blocked"
    lines = [
        "# PPI stable instrument ID allocation artifact review",
        "",
        f"- Status: {status}",
        f"- Source run: {value.get('source_run_id')} attempt {value.get('source_run_attempt')}",
        f"- Artifact mode: {value.get('artifact_mode')}",
        f"- Gate passed: {'yes' if value.get('gate_passed') else 'no'}",
        f"- Candidate count: {value.get('candidate_count', 0)}",
        f"- Allocated: {counts.get('allocated', 0)}",
        f"- Deferred ambiguous: {counts.get('deferred_ambiguous', 0)}",
        f"- Deferred unmatched: {counts.get('deferred_unmatched', 0)}",
        "- Universe snapshot assembled: no",
        "- Registry mutated: no",
        "- Private repository accessed: no",
    ]
    if value.get("blocked_reason"):
        lines.append(f"- Blocked reason: {value['blocked_reason']}")
    if value.get("allocation_snapshot_sha256"):
        lines.append(
            f"- Allocation snapshot SHA-256: `{value['allocation_snapshot_sha256']}`"
        )
    (root / "review.md").write_text("\n".join(lines) + "\n")
    if files_under(root) != {"review.json", "review.md"}:
        raise ReviewError("Review output paths are not exact")


def write_failure(root: Path, message: str, run_id: str, attempt: str) -> None:
    root.mkdir(parents=True, exist_ok=True)
    for child in list(root.iterdir()):
        if child.is_file():
            child.unlink()
    value = {
        "schema_version": "1.0.0",
        "review_contract_id": REVIEW_CONTRACT_ID,
        "status": "failed",
        "gate_passed": False,
        "source_run_id": run_id,
        "source_run_attempt": attempt,
        "reviewed_at_utc": now(),
        "error": message,
        "authority": {
            "universe_snapshot_assembly": False,
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
    (root / "review.json").write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n"
    )
    (root / "review.md").write_text(
        "# PPI stable instrument ID allocation artifact review\n\n"
        f"**Status:** failed closed\n\nReason: {message}\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--source-run-json", type=Path, required=True)
    parser.add_argument("--source-run-id", required=True)
    parser.add_argument("--source-run-attempt", required=True)
    parser.add_argument(
        "--contract",
        type=Path,
        default=Path(
            "contracts/PPI-STABLE-INSTRUMENT-ID-ALLOCATION-PILOT-001-R1.json"
        ),
    )
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    try:
        value = review_artifact(
            artifact_root=args.artifact_root,
            source_run_json=args.source_run_json,
            source_run_id=args.source_run_id,
            source_run_attempt=args.source_run_attempt,
            contract_path=args.contract,
        )
        write_review(args.output_root, value)
        return 0
    except ReviewError as exc:
        write_failure(
            args.output_root, str(exc), args.source_run_id, args.source_run_attempt
        )
        raise


if __name__ == "__main__":
    raise SystemExit(main())
