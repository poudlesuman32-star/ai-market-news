from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

CONTRACT_ID = "PPI-IMMUTABLE-UNIVERSE-SNAPSHOT-PILOT-001-R1"
REVIEW_CONTRACT_ID = "PPI-STABLE-INSTRUMENT-ID-ALLOCATION-ARTIFACT-REVIEW-001-R1"
SOURCE_CONTRACT_ID = "PPI-STABLE-INSTRUMENT-ID-ALLOCATION-PILOT-001-R1"
REVIEW_WORKFLOW_NAME = "PPI stable instrument ID allocation artifact review"
EXPECTED_REPOSITORY = "poudlesuman32-star/ai-market-news"

REVIEW_PATHS = {"review.json", "review.md"}
SOURCE_PATHS = {
    "instrument-id-allocation-500.jsonl",
    "manifest.json",
    "receipt.json",
    "report.md",
}
SUCCESS_PATHS = {
    "universe-instruments.jsonl",
    "universe-deferred.jsonl",
    "manifest.json",
    "receipt.json",
    "report.md",
}
BLOCKED_PATHS = {"blocked.json", "report.md"}

EXPECTED_CANDIDATES = 500
ALLOCATION_STATES = {"allocated", "deferred_ambiguous", "deferred_unmatched"}
EXCHANGES = {"NYSE", "NASDAQ", "NYSE_AMERICAN"}
HEX64 = re.compile(r"^[a-f0-9]{64}$")
CANDIDATE_ID = re.compile(r"^ppi-sec-seed-[a-f0-9]{24}$")
INSTRUMENT_ID = re.compile(r"^ppi-us-equity-[a-f0-9]{24}$")
FIGI = re.compile(r"^[A-Z0-9]{12}$")
CIK = re.compile(r"^[0-9]{10}$")
TICKER = re.compile(r"^[A-Z0-9][A-Z0-9.\-]{0,14}$")

ALLOCATION_FIELDS = {
    "candidate_id",
    "cik",
    "ticker",
    "exchange",
    "source_row_sha256",
    "mapping_status",
    "mapping_record_sha256",
    "allocation_status",
    "instrument_id",
    "identity_key_type",
    "identity_key_value",
    "figi",
    "composite_figi",
    "share_class_figi",
    "identity_input_sha256",
}


class SnapshotError(RuntimeError):
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
        raise SnapshotError(f"Invalid JSON at {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise SnapshotError(f"{path} must contain one object")
    return value


def files_under(root: Path) -> set[str]:
    if not root.is_dir():
        raise SnapshotError(f"Artifact root is missing: {root}")
    paths = {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()}
    if any(path.startswith(".") or "/." in path for path in paths):
        raise SnapshotError("Hidden artifact paths are forbidden")
    return paths


def valid_hex(value: object) -> bool:
    return isinstance(value, str) and bool(HEX64.fullmatch(value))


def optional_figi(value: object) -> bool:
    return value is None or (isinstance(value, str) and bool(FIGI.fullmatch(value)))


def validate_run(value: dict, run_id: str, attempt: str) -> dict:
    if not run_id.isdigit() or not attempt.isdigit():
        raise SnapshotError("Run ID and attempt must be decimal integers")
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
        raise SnapshotError("Review run identity failed: " + ", ".join(failed))
    return checks


def validate_review(
    review_root: Path,
    review_run_json: Path,
    review_run_id: str,
    review_run_attempt: str,
) -> dict:
    if files_under(review_root) != REVIEW_PATHS:
        raise SnapshotError("Allocation review artifact paths are not exact")
    run_checks = validate_run(read_json(review_run_json), review_run_id, review_run_attempt)
    review = read_json(review_root / "review.json")
    core = {key: value for key, value in review.items() if key != "review_core_sha256"}
    authority = review.get("authority") or {}
    counts = review.get("allocation_counts")
    mode = review.get("artifact_mode")
    base_counts_valid = (
        isinstance(counts, dict)
        and set(counts) == ALLOCATION_STATES
        and all(isinstance(value, int) and value >= 0 for value in counts.values())
    )
    success_mode = mode == "success"
    blocked_mode = mode == "blocked"
    checks = {
        "review_contract": review.get("review_contract_id") == REVIEW_CONTRACT_ID,
        "source_contract": review.get("source_contract_id") == SOURCE_CONTRACT_ID,
        "repository": review.get("source_repository") == EXPECTED_REPOSITORY,
        "review_hash": review.get("review_core_sha256") == digest(canon(core)),
        "known_mode": success_mode or blocked_mode,
        "counts_shape": base_counts_valid,
        "mode_counts": (
            success_mode
            and review.get("gate_passed") is True
            and review.get("candidate_count") == EXPECTED_CANDIDATES
            and sum(counts.values()) == EXPECTED_CANDIDATES
        )
        or (
            blocked_mode
            and review.get("gate_passed") is False
            and review.get("candidate_count") == 0
            and sum(counts.values()) == 0
        ),
        "success_hashes": (
            not success_mode
            or (
                valid_hex(review.get("allocation_snapshot_sha256"))
                and valid_hex(review.get("source_snapshot_sha256"))
                and valid_hex(review.get("mapping_snapshot_sha256"))
                and isinstance(review.get("artifact_file_sha256"), dict)
                and set(review["artifact_file_sha256"]) == SOURCE_PATHS
                and all(valid_hex(value) for value in review["artifact_file_sha256"].values())
            )
        ),
        "assembly_authority_false": authority.get("universe_snapshot_assembly") is False,
        "no_private": authority.get("private_access") is False,
        "no_screening": authority.get("screening") is False,
        "no_deep": authority.get("deep_evidence_collection") is False,
        "no_registry": authority.get("registry_mutation") is False,
    }
    failed = [key for key, ok in checks.items() if not ok]
    if failed:
        raise SnapshotError("Allocation review receipt failed: " + ", ".join(failed))
    return {**review, "review_run_checks": run_checks}


def write_github_output(path: str | None, values: dict[str, object]) -> None:
    if not path:
        return
    with Path(path).open("a", encoding="utf-8") as handle:
        for key, value in values.items():
            text = str(value).lower() if isinstance(value, bool) else str(value or "")
            if "\n" in text or "\r" in text:
                raise SnapshotError("GitHub output values must be single-line")
            handle.write(f"{key}={text}\n")


def write_blocked(root: Path, review: dict, reason: str) -> None:
    root.mkdir(parents=True, exist_ok=True)
    if any(root.iterdir()):
        raise SnapshotError("Blocked output root must be empty")
    value = {
        "schema_version": "1.0.0",
        "contract_id": CONTRACT_ID,
        "status": "blocked",
        "reason": reason,
        "review_run_id": review.get("review_run_id"),
        "review_run_attempt": review.get("review_run_attempt"),
        "source_run_id": review.get("source_run_id"),
        "source_run_attempt": review.get("source_run_attempt"),
        "universe_instruments_assembled": 0,
        "deferred_candidates_preserved": 0,
        "network_requests_performed": 0,
        "private_access": False,
        "screening": False,
        "deep_evidence_collection": False,
        "registry_mutation": False,
        "generated_at_utc": now(),
    }
    (root / "blocked.json").write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (root / "report.md").write_text(
        "# PPI immutable universe snapshot pilot\n\n"
        "**Status:** blocked before snapshot assembly\n\n"
        f"Reason: {reason}\n",
        encoding="utf-8",
    )
    if files_under(root) != BLOCKED_PATHS:
        raise SnapshotError("Blocked output paths are not exact")


def write_failure(root: Path, stage: str, message: str, run_id: str, attempt: str) -> None:
    root.mkdir(parents=True, exist_ok=True)
    for child in list(root.iterdir()):
        if child.is_file():
            child.unlink()
    value = {
        "schema_version": "1.0.0",
        "contract_id": CONTRACT_ID,
        "status": "failed",
        "stage": stage,
        "error": message,
        "review_run_id": run_id,
        "review_run_attempt": attempt,
        "network_requests_performed": 0,
        "private_access": False,
        "screening": False,
        "deep_evidence_collection": False,
        "registry_mutation": False,
        "generated_at_utc": now(),
    }
    (root / "failure.json").write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (root / "report.md").write_text(
        "# PPI immutable universe snapshot pilot\n\n"
        "**Status:** failed closed\n\n"
        f"Stage: {stage}\n\nReason: {message}\n",
        encoding="utf-8",
    )


def preflight(
    *,
    review_root: Path,
    review_run_json: Path,
    review_run_id: str,
    review_run_attempt: str,
    output_root: Path,
    github_output: str | None,
) -> dict:
    review = validate_review(review_root, review_run_json, review_run_id, review_run_attempt)
    passed = (
        review.get("gate_passed") is True
        and review.get("artifact_mode") == "success"
        and review.get("candidate_count") == EXPECTED_CANDIDATES
    )
    if not passed:
        write_blocked(
            output_root,
            {**review, "review_run_id": int(review_run_id), "review_run_attempt": int(review_run_attempt)},
            str(review.get("blocked_reason") or "Stable instrument ID allocation review gate did not pass"),
        )
    values = {
        "gate_passed": passed,
        "source_run_id": review.get("source_run_id", ""),
        "source_run_attempt": review.get("source_run_attempt", ""),
        "allocation_snapshot_sha256": review.get("allocation_snapshot_sha256", ""),
    }
    write_github_output(github_output, values)
    return values


def validate_allocation_record(value: object, index: int) -> dict:
    if not isinstance(value, dict) or set(value) != ALLOCATION_FIELDS:
        raise SnapshotError(f"Allocation record {index} fields differ from the frozen schema")
    checks = {
        "candidate_id": isinstance(value["candidate_id"], str) and bool(CANDIDATE_ID.fullmatch(value["candidate_id"])),
        "cik": isinstance(value["cik"], str) and bool(CIK.fullmatch(value["cik"])),
        "ticker": isinstance(value["ticker"], str) and bool(TICKER.fullmatch(value["ticker"])),
        "exchange": value["exchange"] in EXCHANGES,
        "source_row_sha256": valid_hex(value["source_row_sha256"]),
        "mapping_record_sha256": valid_hex(value["mapping_record_sha256"]),
        "allocation_status": value["allocation_status"] in ALLOCATION_STATES,
    }
    failed = [key for key, ok in checks.items() if not ok]
    if failed:
        raise SnapshotError(f"Allocation record {index} failed: " + ", ".join(failed))
    status = value["allocation_status"]
    if status == "allocated":
        figi = value["figi"]
        exact_checks = {
            "mapping_exact": value["mapping_status"] == "exact",
            "figi": isinstance(figi, str) and bool(FIGI.fullmatch(figi)),
            "instrument_id": isinstance(value["instrument_id"], str) and bool(INSTRUMENT_ID.fullmatch(value["instrument_id"])),
            "identity_type": value["identity_key_type"] == "FIGI",
            "identity_value": value["identity_key_value"] == figi,
            "composite_figi": optional_figi(value["composite_figi"]),
            "share_class_figi": optional_figi(value["share_class_figi"]),
            "identity_hash": valid_hex(value["identity_input_sha256"]),
        }
        failed = [key for key, ok in exact_checks.items() if not ok]
        if failed:
            raise SnapshotError(f"Allocation record {index} exact state failed: " + ", ".join(failed))
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
            raise SnapshotError(f"Allocation record {index} deferred state failed: " + ", ".join(failed))
    return value


def validate_allocation_artifact(source_root: Path, review: dict) -> list[dict]:
    if files_under(source_root) != SOURCE_PATHS:
        raise SnapshotError("Stable ID allocation artifact paths are not exact")
    expected_hashes = review["artifact_file_sha256"]
    actual_hashes = {path: digest((source_root / path).read_bytes()) for path in sorted(SOURCE_PATHS)}
    if actual_hashes != expected_hashes:
        raise SnapshotError("Stable ID allocation artifact hashes differ from the review receipt")

    snapshot = (source_root / "instrument-id-allocation-500.jsonl").read_bytes()
    if digest(snapshot) != review.get("allocation_snapshot_sha256"):
        raise SnapshotError("Allocation snapshot hash differs from the review receipt")
    lines = snapshot.splitlines()
    if not snapshot.endswith(b"\n") or len(lines) != EXPECTED_CANDIDATES or any(not line.strip() for line in lines):
        raise SnapshotError("Allocation snapshot must contain exactly 500 canonical JSONL records")
    records = []
    for index, line in enumerate(lines, 1):
        try:
            records.append(validate_allocation_record(json.loads(line), index))
        except json.JSONDecodeError as exc:
            raise SnapshotError(f"Allocation record {index} is invalid JSON: {exc}") from exc
    candidate_ids = [record["candidate_id"] for record in records]
    if candidate_ids != sorted(candidate_ids) or len(set(candidate_ids)) != EXPECTED_CANDIDATES:
        raise SnapshotError("Allocation records must be candidate-ID sorted and unique")
    instrument_ids = [record["instrument_id"] for record in records if record["allocation_status"] == "allocated"]
    if len(instrument_ids) != len(set(instrument_ids)):
        raise SnapshotError("Allocated instrument IDs must be unique")
    counts = {state: sum(record["allocation_status"] == state for record in records) for state in ALLOCATION_STATES}
    if counts != review.get("allocation_counts"):
        raise SnapshotError("Allocation counts differ from the review receipt")

    manifest = read_json(source_root / "manifest.json")
    receipt = read_json(source_root / "receipt.json")
    checks = {
        "manifest_contract": manifest.get("contract_id") == SOURCE_CONTRACT_ID,
        "manifest_snapshot": manifest.get("allocation_snapshot_sha256") == review.get("allocation_snapshot_sha256"),
        "manifest_source_snapshot": manifest.get("source_snapshot_sha256") == review.get("source_snapshot_sha256"),
        "manifest_mapping_snapshot": manifest.get("mapping_snapshot_sha256") == review.get("mapping_snapshot_sha256"),
        "manifest_counts": manifest.get("allocation_counts") == counts,
        "manifest_zero_network": manifest.get("network_requests_performed") == 0,
        "receipt_contract": receipt.get("contract_id") == SOURCE_CONTRACT_ID,
        "receipt_snapshot": receipt.get("allocation_snapshot_sha256") == review.get("allocation_snapshot_sha256"),
        "receipt_run_id": str(receipt.get("run_id")) == str(review.get("source_run_id")),
        "receipt_run_attempt": str(receipt.get("run_attempt")) == str(review.get("source_run_attempt")),
        "receipt_zero_network": receipt.get("network_requests_performed") == 0,
        "receipt_no_private": receipt.get("private_access") is False,
        "receipt_no_screening": receipt.get("screening") is False,
        "receipt_no_deep": receipt.get("deep_evidence_collection") is False,
        "receipt_no_registry": receipt.get("registry_mutation") is False,
    }
    failed = [key for key, ok in checks.items() if not ok]
    if failed:
        raise SnapshotError("Stable ID allocation source artifact failed: " + ", ".join(failed))
    return records


def assemble_records(records: list[dict]) -> tuple[list[dict], list[dict]]:
    if len(records) != EXPECTED_CANDIDATES:
        raise SnapshotError("Exactly 500 allocation records are required")
    instruments: list[dict] = []
    deferred: list[dict] = []
    for record in records:
        allocation_hash = digest(canon(record))
        if record["allocation_status"] == "allocated":
            instruments.append(
                {
                    "schema_version": "1.0.0",
                    "instrument_id": record["instrument_id"],
                    "identity_status": "verified_exact_figi",
                    "lifecycle_state": "universe_member",
                    "classification_status": "unresolved_asset_subtype",
                    "figi": record["figi"],
                    "composite_figi": record["composite_figi"],
                    "share_class_figi": record["share_class_figi"],
                    "cik": record["cik"],
                    "current_symbol": record["ticker"],
                    "exchange": record["exchange"],
                    "source_candidate_id": record["candidate_id"],
                    "source_row_sha256": record["source_row_sha256"],
                    "allocation_record_sha256": allocation_hash,
                    "symbol_aliases": [
                        {"symbol": record["ticker"], "exchange": record["exchange"], "status": "current"}
                    ],
                }
            )
        else:
            deferred.append(
                {
                    "schema_version": "1.0.0",
                    "candidate_id": record["candidate_id"],
                    "cik": record["cik"],
                    "ticker": record["ticker"],
                    "exchange": record["exchange"],
                    "mapping_status": record["mapping_status"],
                    "disposition": record["allocation_status"],
                    "reason": (
                        "ambiguous_external_identity"
                        if record["allocation_status"] == "deferred_ambiguous"
                        else "unmatched_external_identity"
                    ),
                    "source_row_sha256": record["source_row_sha256"],
                    "allocation_record_sha256": allocation_hash,
                }
            )
    instruments.sort(key=lambda item: item["instrument_id"])
    deferred.sort(key=lambda item: item["candidate_id"])
    if len({item["instrument_id"] for item in instruments}) != len(instruments):
        raise SnapshotError("Universe instruments contain duplicate stable IDs")
    if len(instruments) + len(deferred) != EXPECTED_CANDIDATES:
        raise SnapshotError("Universe and deferred records do not sum to 500")
    return instruments, deferred


def write_outputs(
    root: Path,
    review: dict,
    instruments: list[dict],
    deferred: list[dict],
    contract_path: Path,
) -> None:
    root.mkdir(parents=True, exist_ok=True)
    if any(root.iterdir()):
        raise SnapshotError("Snapshot output root must be empty")
    instrument_bytes = b"".join(canon(record) for record in instruments)
    deferred_bytes = b"".join(canon(record) for record in deferred)
    instrument_hash = digest(instrument_bytes)
    deferred_hash = digest(deferred_bytes)
    combined_hash = digest(
        canon(
            {
                "allocation_snapshot_sha256": review["allocation_snapshot_sha256"],
                "universe_instruments_sha256": instrument_hash,
                "universe_deferred_sha256": deferred_hash,
            }
        )
    )
    generated_at = now()
    core = {
        "schema_version": "1.0.0",
        "contract_id": CONTRACT_ID,
        "snapshot_id": f"ppi-universe-pilot-{combined_hash[:16]}",
        "generated_at_utc": generated_at,
        "candidate_count": EXPECTED_CANDIDATES,
        "instrument_count": len(instruments),
        "deferred_count": len(deferred),
        "allocation_counts": review["allocation_counts"],
        "source_snapshot_sha256": review["source_snapshot_sha256"],
        "mapping_snapshot_sha256": review["mapping_snapshot_sha256"],
        "allocation_snapshot_sha256": review["allocation_snapshot_sha256"],
        "universe_instruments_sha256": instrument_hash,
        "universe_deferred_sha256": deferred_hash,
        "combined_snapshot_sha256": combined_hash,
        "previous_snapshot_sha256": None,
        "lifecycle_state": "universe_member",
        "classification_status": "unresolved_asset_subtype",
        "deferred_candidates_preserved": True,
        "network_requests_performed": 0,
    }
    manifest = {**core, "manifest_core_sha256": digest(canon(core))}
    receipt = {
        "schema_version": "1.0.0",
        "contract_id": CONTRACT_ID,
        "contract_sha256": digest(contract_path.read_bytes()),
        "repository": os.environ.get("GITHUB_REPOSITORY", "local"),
        "run_id": os.environ.get("GITHUB_RUN_ID"),
        "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        "event_name": os.environ.get("GITHUB_EVENT_NAME"),
        "head_sha": os.environ.get("GITHUB_SHA"),
        "generated_at_utc": generated_at,
        "source_review_run_id": review["review_run_id"],
        "source_review_run_attempt": review["review_run_attempt"],
        "source_allocation_run_id": review["source_run_id"],
        "source_allocation_run_attempt": review["source_run_attempt"],
        "allocation_snapshot_sha256": review["allocation_snapshot_sha256"],
        "universe_instruments_sha256": instrument_hash,
        "universe_deferred_sha256": deferred_hash,
        "combined_snapshot_sha256": combined_hash,
        "manifest_core_sha256": manifest["manifest_core_sha256"],
        "universe_instruments_assembled": len(instruments),
        "deferred_candidates_preserved": len(deferred),
        "network_requests_performed": 0,
        "private_access": False,
        "screening": False,
        "deep_evidence_collection": False,
        "private_dispatch": False,
        "billing_budget_mutation": False,
        "registry_mutation": False,
        "production": False,
        "publication": False,
        "trading": False,
        "authorized_actions": ["immutable_universe_snapshot_assembly_public_pilot"],
    }
    (root / "universe-instruments.jsonl").write_bytes(instrument_bytes)
    (root / "universe-deferred.jsonl").write_bytes(deferred_bytes)
    (root / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (root / "receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (root / "report.md").write_text(
        "# PPI immutable 500-candidate universe snapshot pilot\n\n"
        "- Status: success\n"
        f"- Candidate count: {EXPECTED_CANDIDATES}\n"
        f"- Universe instruments: {len(instruments)}\n"
        f"- Deferred candidates: {len(deferred)}\n"
        "- Classification status: unresolved_asset_subtype\n"
        "- Network requests performed: 0\n"
        "- Private repository accessed: no\n"
        "- Screening or deep evidence performed: no\n"
        "- Registry mutated: no\n",
        encoding="utf-8",
    )
    if files_under(root) != SUCCESS_PATHS:
        raise SnapshotError("Success output paths are not exact")


def execute_snapshot(
    *,
    review_root: Path,
    review_run_json: Path,
    review_run_id: str,
    review_run_attempt: str,
    source_root: Path,
    output_root: Path,
    contract_path: Path,
) -> dict:
    review = validate_review(review_root, review_run_json, review_run_id, review_run_attempt)
    if not (
        review.get("gate_passed") is True
        and review.get("artifact_mode") == "success"
        and review.get("candidate_count") == EXPECTED_CANDIDATES
    ):
        raise SnapshotError("Universe snapshot assembly requires an exact passed allocation review")
    records = validate_allocation_artifact(source_root, review)
    instruments, deferred = assemble_records(records)
    write_outputs(
        output_root,
        {**review, "review_run_id": int(review_run_id), "review_run_attempt": int(review_run_attempt)},
        instruments,
        deferred,
        contract_path,
    )
    return {
        "candidate_count": EXPECTED_CANDIDATES,
        "instrument_count": len(instruments),
        "deferred_count": len(deferred),
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
    run = sub.add_parser("assemble")
    run.add_argument("--review-root", type=Path, required=True)
    run.add_argument("--review-run-json", type=Path, required=True)
    run.add_argument("--review-run-id", required=True)
    run.add_argument("--review-run-attempt", required=True)
    run.add_argument("--source-root", type=Path, required=True)
    run.add_argument("--output-root", type=Path, required=True)
    run.add_argument(
        "--contract",
        type=Path,
        default=Path("contracts/PPI-IMMUTABLE-UNIVERSE-SNAPSHOT-PILOT-001-R1.json"),
    )
    args = parser.parse_args()
    try:
        if args.command == "preflight":
            preflight(
                review_root=args.review_root,
                review_run_json=args.review_run_json,
                review_run_id=args.review_run_id,
                review_run_attempt=args.review_run_attempt,
                output_root=args.output_root,
                github_output=args.github_output,
            )
        else:
            execute_snapshot(
                review_root=args.review_root,
                review_run_json=args.review_run_json,
                review_run_id=args.review_run_id,
                review_run_attempt=args.review_run_attempt,
                source_root=args.source_root,
                output_root=args.output_root,
                contract_path=args.contract,
            )
        return 0
    except SnapshotError as exc:
        write_failure(args.output_root, args.command, str(exc), args.review_run_id, args.review_run_attempt)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
