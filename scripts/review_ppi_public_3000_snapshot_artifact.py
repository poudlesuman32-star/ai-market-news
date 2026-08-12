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


def review(root: Path) -> dict:
    validation = validator.validate_snapshot(root)
    if validation["artifact_mode"] == "blocked":
        blocked = load_json(root / "blocked.json")
        if blocked.get("artifact_mode") not in {None, "blocked"}:
            raise ReviewError("blocked artifact declares incompatible mode")
        return {"gate_passed": False, "artifact_mode": "blocked", "total_candidate_dispositions": 0}

    manifest = load_json(root / "manifest.json")
    receipt = load_json(root / "receipt.json")

    if manifest.get("contract_id") != validator.CONTRACT_ID:
        raise ReviewError("manifest contract_id mismatch")
    if receipt.get("contract_id") != validator.CONTRACT_ID:
        raise ReviewError("receipt contract_id mismatch")
    if manifest.get("artifact_mode") != "success" or receipt.get("artifact_mode") != "success":
        raise ReviewError("success artifact mode mismatch")

    actual_hashes = {name: sha256_bytes((root / name).read_bytes()) for name in DATA_PATHS}
    if manifest.get("data_file_sha256") != actual_hashes:
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
    required_source = ("review_run_id", "review_run_attempt", "review_artifact_id", "review_receipt_sha256")
    if any(source.get(key) in (None, "") for key in required_source):
        raise ReviewError("incomplete step-8 review lineage")
    if not validator.HEX64.fullmatch(str(source["review_receipt_sha256"])):
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
