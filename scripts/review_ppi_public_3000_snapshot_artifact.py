from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = ROOT / "scripts" / "validate_ppi_public_3000_snapshot_contract.py"
SPEC = importlib.util.spec_from_file_location("step9_validator", VALIDATOR_PATH)
validator = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(validator)

DATA_PATHS = ("universe-instruments-3000.jsonl", "universe-deferred-3000.jsonl")
MANIFEST_KEYS = {"contract_id", "artifact_mode", "data_file_sha256", "combined_snapshot_sha256", "step8_source"}
RECEIPT_KEYS = {"contract_id", "artifact_mode", "gate_passed", "total_candidate_dispositions", "combined_snapshot_sha256"}
STEP8_SOURCE_KEYS = {"review_run_id", "review_run_attempt", "review_artifact_id", "review_receipt_sha256"}


class ReviewError(RuntimeError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_json_sha256(value: object) -> str:
    return sha256_bytes(validator.canon(value))


def load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ReviewError(f"{path.name} must contain one JSON object")
    return value


def load_jsonl(path: Path) -> list[dict]:
    values: list[dict] = []
    for line in path.read_bytes().splitlines():
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ReviewError(f"{path.name} must contain JSON objects")
        values.append(value)
    return values


def require_exact_keys(value: dict, expected: set[str], label: str) -> None:
    if set(value) != expected:
        raise ReviewError(f"{label} fields differ from frozen schema")


def require_deterministic_partition(root: Path) -> None:
    allocated = load_jsonl(root / "universe-instruments-3000.jsonl")
    deferred = load_jsonl(root / "universe-deferred-3000.jsonl")

    if any(value.get("disposition") != "allocated" for value in allocated):
        raise ReviewError("allocated file contains a non-allocated disposition")
    if any(value.get("disposition") not in {"deferred_ambiguous", "deferred_unmatched"} for value in deferred):
        raise ReviewError("deferred file contains an allocated or unknown disposition")

    allocated_ids = [value.get("candidate_id") for value in allocated]
    deferred_ids = [value.get("candidate_id") for value in deferred]
    if allocated_ids != sorted(allocated_ids):
        raise ReviewError("allocated records are not deterministically ordered by candidate_id")
    if deferred_ids != sorted(deferred_ids):
        raise ReviewError("deferred records are not deterministically ordered by candidate_id")
    if set(allocated_ids) & set(deferred_ids):
        raise ReviewError("allocated and deferred candidate sets overlap")


def review(root: Path) -> dict:
    validation = validator.validate_snapshot(root)
    if validation["artifact_mode"] == "blocked":
        blocked = load_json(root / "blocked.json")
        if blocked.get("artifact_mode") not in {None, "blocked"}:
            raise ReviewError("blocked artifact declares incompatible mode")
        return {"gate_passed": False, "artifact_mode": "blocked", "total_candidate_dispositions": 0}

    require_deterministic_partition(root)
    manifest = load_json(root / "manifest.json")
    receipt = load_json(root / "receipt.json")
    require_exact_keys(manifest, MANIFEST_KEYS, "manifest")
    require_exact_keys(receipt, RECEIPT_KEYS, "receipt")

    if manifest.get("contract_id") != validator.CONTRACT_ID:
        raise ReviewError("manifest contract_id mismatch")
    if receipt.get("contract_id") != validator.CONTRACT_ID:
        raise ReviewError("receipt contract_id mismatch")
    if manifest.get("artifact_mode") != "success" or receipt.get("artifact_mode") != "success":
        raise ReviewError("success artifact mode mismatch")

    actual_hashes = {name: sha256_bytes((root / name).read_bytes()) for name in DATA_PATHS}
    declared_hashes = manifest.get("data_file_sha256")
    if not isinstance(declared_hashes, dict) or set(declared_hashes) != set(DATA_PATHS):
        raise ReviewError("manifest data-file hash keys differ from frozen schema")
    if declared_hashes != actual_hashes:
        raise ReviewError("manifest data-file hashes do not match retained bytes")

    combined_input = {name: actual_hashes[name] for name in sorted(actual_hashes)}
    combined_hash = canonical_json_sha256(combined_input)
    if manifest.get("combined_snapshot_sha256") != combined_hash:
        raise ReviewError("combined snapshot hash mismatch")

    if receipt.get("total_candidate_dispositions") != validator.EXPECTED_COUNT:
        raise ReviewError("receipt disposition count mismatch")
    if receipt.get("combined_snapshot_sha256") != combined_hash:
        raise ReviewError("receipt snapshot hash mismatch")
    if receipt.get("gate_passed") is not True:
        raise ReviewError("producer receipt does not claim a passing gate")

    source = manifest.get("step8_source")
    if not isinstance(source, dict):
        raise ReviewError("manifest missing step-8 source binding")
    require_exact_keys(source, STEP8_SOURCE_KEYS, "step-8 source")
    for key in ("review_run_id", "review_run_attempt", "review_artifact_id"):
        if type(source.get(key)) is not int or source[key] < 1:
            raise ReviewError(f"invalid step-8 {key}")
    receipt_hash = source.get("review_receipt_sha256")
    if not isinstance(receipt_hash, str) or not validator.HEX64.fullmatch(receipt_hash):
        raise ReviewError("invalid step-8 review receipt hash")

    return {
        "gate_passed": True,
        "artifact_mode": "success",
        "total_candidate_dispositions": validator.EXPECTED_COUNT,
        "combined_snapshot_sha256": combined_hash,
        "review_network_requests": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("artifact_root")
    args = parser.parse_args()
    print(json.dumps(review(Path(args.artifact_root)), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
