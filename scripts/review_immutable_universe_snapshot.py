from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
import assemble_immutable_universe_snapshot as assembler

REVIEW_CONTRACT_ID = "PPI-IMMUTABLE-UNIVERSE-SNAPSHOT-ARTIFACT-REVIEW-001-R1"
SOURCE_CONTRACT_ID = assembler.CONTRACT_ID
SOURCE_WORKFLOW_NAME = "PPI immutable 500-instrument universe snapshot pilot"
EXPECTED_REPOSITORY = assembler.EXPECTED_REPOSITORY
SUCCESS_PATHS = assembler.SUCCESS_PATHS
BLOCKED_PATHS = assembler.BLOCKED_PATHS
EXPECTED_CANDIDATES = assembler.EXPECTED_CANDIDATES

INSTRUMENT_FIELDS = {
    "schema_version",
    "instrument_id",
    "identity_status",
    "lifecycle_state",
    "classification_status",
    "figi",
    "composite_figi",
    "share_class_figi",
    "cik",
    "current_symbol",
    "exchange",
    "source_candidate_id",
    "source_row_sha256",
    "allocation_record_sha256",
    "symbol_aliases",
}
DEFERRED_FIELDS = {
    "schema_version",
    "candidate_id",
    "cik",
    "ticker",
    "exchange",
    "mapping_status",
    "disposition",
    "reason",
    "source_row_sha256",
    "allocation_record_sha256",
}
DEFERRED_DISPOSITIONS = {"deferred_ambiguous", "deferred_unmatched"}


class ReviewError(RuntimeError):
    pass


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def canon(value: object) -> bytes:
    return assembler.canon(value)


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
        return assembler.files_under(root)
    except assembler.SnapshotError as exc:
        raise ReviewError(str(exc)) from exc


def valid_hex(value: object) -> bool:
    return assembler.valid_hex(value)


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
        "zero_instruments": value.get("universe_instruments_assembled") == 0,
        "zero_deferred": value.get("deferred_candidates_preserved") == 0,
        "zero_network": value.get("network_requests_performed") == 0,
        "no_private": value.get("private_access") is False,
        "no_screening": value.get("screening") is False,
        "no_deep": value.get("deep_evidence_collection") is False,
        "no_registry": value.get("registry_mutation") is False,
    }
    failed = [key for key, ok in checks.items() if not ok]
    if failed:
        raise ReviewError("Blocked snapshot artifact failed: " + ", ".join(failed))
    return {
        "artifact_mode": "blocked",
        "gate_passed": False,
        "candidate_count": 0,
        "instrument_count": 0,
        "deferred_count": 0,
        "blocked_reason": str(value.get("reason") or "unspecified"),
        "checks": checks,
    }


def validate_instrument(value: object, index: int) -> dict:
    if not isinstance(value, dict) or set(value) != INSTRUMENT_FIELDS:
        raise ReviewError(f"Instrument record {index} fields differ from the frozen schema")
    aliases = value["symbol_aliases"]
    checks = {
        "schema": value["schema_version"] == "1.0.0",
        "instrument_id": isinstance(value["instrument_id"], str)
        and bool(assembler.INSTRUMENT_ID.fullmatch(value["instrument_id"])),
        "identity_status": value["identity_status"] == "verified_exact_figi",
        "lifecycle": value["lifecycle_state"] == "universe_member",
        "classification": value["classification_status"] == "unresolved_asset_subtype",
        "figi": isinstance(value["figi"], str)
        and bool(assembler.FIGI.fullmatch(value["figi"])),
        "composite_figi": assembler.optional_figi(value["composite_figi"]),
        "share_class_figi": assembler.optional_figi(value["share_class_figi"]),
        "cik": isinstance(value["cik"], str) and bool(assembler.CIK.fullmatch(value["cik"])),
        "symbol": isinstance(value["current_symbol"], str)
        and bool(assembler.TICKER.fullmatch(value["current_symbol"])),
        "exchange": value["exchange"] in assembler.EXCHANGES,
        "candidate": isinstance(value["source_candidate_id"], str)
        and bool(assembler.CANDIDATE_ID.fullmatch(value["source_candidate_id"])),
        "source_hash": valid_hex(value["source_row_sha256"]),
        "allocation_hash": valid_hex(value["allocation_record_sha256"]),
        "alias_shape": isinstance(aliases, list) and len(aliases) == 1,
    }
    if checks["alias_shape"]:
        checks.update(
            {
                "alias_fields": set(aliases[0]) == {"symbol", "exchange", "status"},
                "alias_symbol": aliases[0].get("symbol") == value["current_symbol"],
                "alias_exchange": aliases[0].get("exchange") == value["exchange"],
                "alias_status": aliases[0].get("status") == "current",
            }
        )
    failed = [key for key, ok in checks.items() if not ok]
    if failed:
        raise ReviewError(f"Instrument record {index} failed: " + ", ".join(failed))
    return value


def validate_deferred(value: object, index: int) -> dict:
    if not isinstance(value, dict) or set(value) != DEFERRED_FIELDS:
        raise ReviewError(f"Deferred record {index} fields differ from the frozen schema")
    disposition = value["disposition"]
    expected_mapping = disposition.removeprefix("deferred_") if isinstance(disposition, str) else ""
    expected_reason = (
        "ambiguous_external_identity"
        if disposition == "deferred_ambiguous"
        else "unmatched_external_identity"
    )
    checks = {
        "schema": value["schema_version"] == "1.0.0",
        "candidate": isinstance(value["candidate_id"], str)
        and bool(assembler.CANDIDATE_ID.fullmatch(value["candidate_id"])),
        "cik": isinstance(value["cik"], str) and bool(assembler.CIK.fullmatch(value["cik"])),
        "ticker": isinstance(value["ticker"], str)
        and bool(assembler.TICKER.fullmatch(value["ticker"])),
        "exchange": value["exchange"] in assembler.EXCHANGES,
        "disposition": disposition in DEFERRED_DISPOSITIONS,
        "mapping": value["mapping_status"] == expected_mapping,
        "reason": value["reason"] == expected_reason,
        "source_hash": valid_hex(value["source_row_sha256"]),
        "allocation_hash": valid_hex(value["allocation_record_sha256"]),
    }
    failed = [key for key, ok in checks.items() if not ok]
    if failed:
        raise ReviewError(f"Deferred record {index} failed: " + ", ".join(failed))
    return value


def read_jsonl(path: Path, validator) -> tuple[bytes, list[dict]]:
    payload = path.read_bytes()
    if payload and not payload.endswith(b"\n"):
        raise ReviewError(f"{path.name} must end with one newline")
    lines = payload.splitlines()
    if any(not line.strip() for line in lines):
        raise ReviewError(f"{path.name} contains an empty JSONL record")
    records = []
    for index, line in enumerate(lines, 1):
        try:
            records.append(validator(json.loads(line), index))
        except json.JSONDecodeError as exc:
            raise ReviewError(f"{path.name} record {index} is invalid JSON: {exc}") from exc
    return payload, records


def validate_success(root: Path, contract_path: Path, run_id: str, attempt: str) -> dict:
    instrument_bytes, instruments = read_jsonl(root / "universe-instruments.jsonl", validate_instrument)
    deferred_bytes, deferred = read_jsonl(root / "universe-deferred.jsonl", validate_deferred)
    if len(instruments) + len(deferred) != EXPECTED_CANDIDATES:
        raise ReviewError("Universe and deferred snapshots must sum to 500 candidates")

    instrument_ids = [record["instrument_id"] for record in instruments]
    instrument_candidates = [record["source_candidate_id"] for record in instruments]
    deferred_candidates = [record["candidate_id"] for record in deferred]
    if instrument_ids != sorted(instrument_ids) or len(set(instrument_ids)) != len(instrument_ids):
        raise ReviewError("Universe instrument IDs must be sorted and unique")
    if deferred_candidates != sorted(deferred_candidates) or len(set(deferred_candidates)) != len(deferred_candidates):
        raise ReviewError("Deferred candidate IDs must be sorted and unique")
    if len(set(instrument_candidates)) != len(instrument_candidates):
        raise ReviewError("Universe source candidate IDs must be unique")
    if set(instrument_candidates) & set(deferred_candidates):
        raise ReviewError("Universe and deferred candidate sets overlap")

    instrument_hash = digest(instrument_bytes)
    deferred_hash = digest(deferred_bytes)
    manifest = read_json(root / "manifest.json")
    core = {key: value for key, value in manifest.items() if key != "manifest_core_sha256"}
    combined_hash = digest(
        canon(
            {
                "allocation_snapshot_sha256": manifest.get("allocation_snapshot_sha256"),
                "universe_instruments_sha256": instrument_hash,
                "universe_deferred_sha256": deferred_hash,
            }
        )
    )
    counts = manifest.get("allocation_counts")
    expected_counts = {
        "allocated": len(instruments),
        "deferred_ambiguous": sum(item["disposition"] == "deferred_ambiguous" for item in deferred),
        "deferred_unmatched": sum(item["disposition"] == "deferred_unmatched" for item in deferred),
    }
    checks = {
        "manifest_contract": manifest.get("contract_id") == SOURCE_CONTRACT_ID,
        "manifest_candidate_count": manifest.get("candidate_count") == EXPECTED_CANDIDATES,
        "manifest_instrument_count": manifest.get("instrument_count") == len(instruments),
        "manifest_deferred_count": manifest.get("deferred_count") == len(deferred),
        "manifest_counts": counts == expected_counts,
        "manifest_source_hash": valid_hex(manifest.get("source_snapshot_sha256")),
        "manifest_mapping_hash": valid_hex(manifest.get("mapping_snapshot_sha256")),
        "manifest_allocation_hash": valid_hex(manifest.get("allocation_snapshot_sha256")),
        "manifest_instrument_hash": manifest.get("universe_instruments_sha256") == instrument_hash,
        "manifest_deferred_hash": manifest.get("universe_deferred_sha256") == deferred_hash,
        "manifest_combined_hash": manifest.get("combined_snapshot_sha256") == combined_hash,
        "manifest_snapshot_id": manifest.get("snapshot_id") == f"ppi-universe-pilot-{combined_hash[:16]}",
        "manifest_previous": manifest.get("previous_snapshot_sha256") is None,
        "manifest_lifecycle": manifest.get("lifecycle_state") == "universe_member",
        "manifest_classification": manifest.get("classification_status") == "unresolved_asset_subtype",
        "manifest_preserved": manifest.get("deferred_candidates_preserved") is True,
        "manifest_zero_network": manifest.get("network_requests_performed") == 0,
        "manifest_hash": manifest.get("manifest_core_sha256") == digest(canon(core)),
    }

    receipt = read_json(root / "receipt.json")
    checks.update(
        {
            "receipt_contract": receipt.get("contract_id") == SOURCE_CONTRACT_ID,
            "receipt_contract_hash": receipt.get("contract_sha256") == digest(contract_path.read_bytes()),
            "receipt_repository": receipt.get("repository") == EXPECTED_REPOSITORY,
            "receipt_run_id": str(receipt.get("run_id")) == run_id,
            "receipt_run_attempt": str(receipt.get("run_attempt")) == attempt,
            "receipt_allocation_hash": receipt.get("allocation_snapshot_sha256") == manifest.get("allocation_snapshot_sha256"),
            "receipt_instrument_hash": receipt.get("universe_instruments_sha256") == instrument_hash,
            "receipt_deferred_hash": receipt.get("universe_deferred_sha256") == deferred_hash,
            "receipt_combined_hash": receipt.get("combined_snapshot_sha256") == combined_hash,
            "receipt_manifest": receipt.get("manifest_core_sha256") == manifest.get("manifest_core_sha256"),
            "receipt_instruments": receipt.get("universe_instruments_assembled") == len(instruments),
            "receipt_deferred": receipt.get("deferred_candidates_preserved") == len(deferred),
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
            "receipt_authority": receipt.get("authorized_actions") == ["immutable_universe_snapshot_assembly_public_pilot"],
        }
    )

    report = (root / "report.md").read_text(encoding="utf-8")
    checks.update(
        {
            "report_success": "- Status: success" in report,
            "report_candidates": "- Candidate count: 500" in report,
            "report_instruments": f"- Universe instruments: {len(instruments)}" in report,
            "report_deferred": f"- Deferred candidates: {len(deferred)}" in report,
            "report_unresolved": "- Classification status: unresolved_asset_subtype" in report,
        }
    )
    failed = [key for key, ok in checks.items() if not ok]
    if failed:
        raise ReviewError("Success snapshot artifact failed: " + ", ".join(failed))

    return {
        "artifact_mode": "success",
        "gate_passed": True,
        "candidate_count": EXPECTED_CANDIDATES,
        "instrument_count": len(instruments),
        "deferred_count": len(deferred),
        "allocation_counts": expected_counts,
        "source_snapshot_sha256": manifest["source_snapshot_sha256"],
        "mapping_snapshot_sha256": manifest["mapping_snapshot_sha256"],
        "allocation_snapshot_sha256": manifest["allocation_snapshot_sha256"],
        "universe_instruments_sha256": instrument_hash,
        "universe_deferred_sha256": deferred_hash,
        "combined_snapshot_sha256": combined_hash,
        "manifest_core_sha256": manifest["manifest_core_sha256"],
        "artifact_file_sha256": {path: digest((root / path).read_bytes()) for path in sorted(SUCCESS_PATHS)},
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
            "asset_classification": False,
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
    (root / "review.json").write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    status = "passed" if value.get("gate_passed") else "blocked"
    lines = [
        "# PPI immutable universe snapshot artifact review",
        "",
        f"- Status: {status}",
        f"- Source run: {value.get('source_run_id')} attempt {value.get('source_run_attempt')}",
        f"- Artifact mode: {value.get('artifact_mode')}",
        f"- Gate passed: {'yes' if value.get('gate_passed') else 'no'}",
        f"- Candidate count: {value.get('candidate_count', 0)}",
        f"- Universe instruments: {value.get('instrument_count', 0)}",
        f"- Deferred candidates: {value.get('deferred_count', 0)}",
        "- Asset classification performed: no",
        "- Screening or deep evidence performed: no",
        "- Registry mutated: no",
        "- Private repository accessed: no",
    ]
    if value.get("blocked_reason"):
        lines.append(f"- Blocked reason: {value['blocked_reason']}")
    if value.get("combined_snapshot_sha256"):
        lines.append(f"- Combined snapshot SHA-256: `{value['combined_snapshot_sha256']}`")
    (root / "review.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
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
            "asset_classification": False,
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
    (root / "review.json").write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (root / "review.md").write_text(
        "# PPI immutable universe snapshot artifact review\n\n"
        f"**Status:** failed closed\n\nReason: {message}\n",
        encoding="utf-8",
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
        default=Path("contracts/PPI-IMMUTABLE-UNIVERSE-SNAPSHOT-PILOT-001-R1.json"),
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
        write_failure(args.output_root, str(exc), args.source_run_id, args.source_run_attempt)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
