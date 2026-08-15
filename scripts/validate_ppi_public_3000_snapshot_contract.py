from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

CONTRACT_ID = "PPI-PUBLIC-3000-SNAPSHOT-001-R1"
EXPECTED_COUNT = 3000
SUCCESS_PATHS = {
    "manifest.json",
    "receipt.json",
    "report.md",
    "universe-deferred-3000.jsonl",
    "universe-instruments-3000.jsonl",
}
BLOCKED_PATHS = {"blocked.json", "report.md"}
RECORD_FIELDS = {
    "candidate_id",
    "cik",
    "ticker",
    "exchange",
    "disposition",
    "instrument_id",
    "figi",
    "identity_status",
    "classification_status",
    "source_row_sha256",
}
HEX64 = re.compile(r"^[a-f0-9]{64}$")
CANDIDATE_ID = re.compile(r"^ppi-sec-seed-[a-f0-9]{24}$")
CIK = re.compile(r"^[0-9]{10}$")
TICKER = re.compile(r"^[A-Z0-9][A-Z0-9.\-]{0,14}$")
INSTRUMENT_ID = re.compile(r"^ppi-us-equity-[a-f0-9]{24}$")
FIGI = re.compile(r"^[A-Z0-9]{12}$")
EXCHANGES = {"NYSE", "NASDAQ", "NYSE_AMERICAN"}


class ContractError(RuntimeError):
    pass


def canon(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode()


def stable_instrument_id(figi: str) -> str:
    payload = f"PPI-STABLE-INSTRUMENT-ID-V1|FIGI|{figi}".encode()
    return "ppi-us-equity-" + hashlib.sha256(payload).hexdigest()[:24]


def load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ContractError(f"{path} must contain one JSON object")
    return value


def validate_contract(path: Path) -> dict:
    value = load_json(path)
    if value.get("contract_id") != CONTRACT_ID:
        raise ContractError("unexpected contract_id")
    if value.get("canonical_plan_step") != 9:
        raise ContractError("contract must bind canonical step 9")
    if value.get("required_total_candidate_dispositions") != EXPECTED_COUNT:
        raise ContractError("contract must require exactly 3000 dispositions")
    if set(value.get("success_paths") or []) != SUCCESS_PATHS:
        raise ContractError("success path set is not frozen")
    if set(value.get("blocked_paths") or []) != BLOCKED_PATHS:
        raise ContractError("blocked path set is not frozen")
    gate = value.get("entry_gate") or {}
    if gate.get("step8_review_receipt_required") is not True or gate.get("live_execution_authorized") is not False:
        raise ContractError("step-8 gate or execution hold is not fail-closed")
    authority = value.get("authority") or {}
    forbidden = {
        "network_access",
        "provider_acquisition",
        "private_access",
        "private_dispatch",
        "billing_budget_mutation",
        "registry_mutation",
        "production",
        "publication",
        "broker",
        "orders",
        "trading",
    }
    if any(authority.get(key) is not False for key in forbidden):
        raise ContractError("forbidden authority enabled")
    return value


def validate_record(value: dict) -> None:
    if not isinstance(value, dict) or set(value) != RECORD_FIELDS:
        raise ContractError("record fields differ from frozen schema")
    if not isinstance(value["candidate_id"], str) or not CANDIDATE_ID.fullmatch(value["candidate_id"]):
        raise ContractError("invalid candidate_id")
    if not isinstance(value["cik"], str) or not CIK.fullmatch(value["cik"]):
        raise ContractError("invalid cik")
    if not isinstance(value["ticker"], str) or not TICKER.fullmatch(value["ticker"]):
        raise ContractError("invalid ticker")
    if value["exchange"] not in EXCHANGES:
        raise ContractError("invalid exchange")
    if value["classification_status"] != "unresolved_asset_subtype":
        raise ContractError("classification must remain unresolved_asset_subtype")
    if not isinstance(value["source_row_sha256"], str) or not HEX64.fullmatch(value["source_row_sha256"]):
        raise ContractError("invalid source row hash")

    disposition = value["disposition"]
    if disposition == "allocated":
        figi = value["figi"]
        instrument_id = value["instrument_id"]
        if not isinstance(figi, str) or not FIGI.fullmatch(figi):
            raise ContractError("allocated record requires exact FIGI")
        if not isinstance(instrument_id, str) or not INSTRUMENT_ID.fullmatch(instrument_id):
            raise ContractError("allocated record requires stable instrument ID")
        if instrument_id != stable_instrument_id(figi):
            raise ContractError("stable instrument ID does not match established algorithm")
        if value["identity_status"] != "verified_exact_figi":
            raise ContractError("allocated identity status mismatch")
    elif disposition in {"deferred_ambiguous", "deferred_unmatched"}:
        if value["instrument_id"] is not None:
            raise ContractError("deferred record must not receive an instrument ID")
        figi = value["figi"]
        if figi is not None and (not isinstance(figi, str) or not FIGI.fullmatch(figi)):
            raise ContractError("deferred FIGI must be null or schema-valid")
        if value["identity_status"] != disposition:
            raise ContractError("deferred identity status mismatch")
    else:
        raise ContractError("unknown disposition")


def validate_snapshot(root: Path) -> dict:
    paths = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}
    if paths == BLOCKED_PATHS:
        return {"artifact_mode": "blocked", "gate_passed": False, "total_candidate_dispositions": 0}
    if paths != SUCCESS_PATHS:
        raise ContractError("artifact paths differ from frozen success or blocked set")

    records: list[dict] = []
    for name in ("universe-instruments-3000.jsonl", "universe-deferred-3000.jsonl"):
        data = (root / name).read_bytes()
        if data and not data.endswith(b"\n"):
            raise ContractError(f"{name} must end with a newline")
        for line in data.splitlines():
            value = json.loads(line)
            if not isinstance(value, dict) or canon(value).rstrip(b"\n") != line:
                raise ContractError(f"{name} contains non-canonical JSONL")
            validate_record(value)
            records.append(value)

    if len(records) != EXPECTED_COUNT:
        raise ContractError("snapshot must contain exactly 3000 dispositions")
    candidate_ids = [v["candidate_id"] for v in records]
    if len(set(candidate_ids)) != EXPECTED_COUNT:
        raise ContractError("candidate identities must be unique")
    instrument_ids = [v["instrument_id"] for v in records if v["instrument_id"] is not None]
    if len(instrument_ids) != len(set(instrument_ids)):
        raise ContractError("stable instrument IDs must be unique")
    return {"artifact_mode": "success", "gate_passed": True, "total_candidate_dispositions": EXPECTED_COUNT}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", default="contracts/PPI-PUBLIC-3000-SNAPSHOT-001-R1.json")
    parser.add_argument("--artifact-root")
    args = parser.parse_args()
    validate_contract(Path(args.contract))
    if args.artifact_root:
        print(json.dumps(validate_snapshot(Path(args.artifact_root)), sort_keys=True))
    else:
        print(json.dumps({"contract_valid": True, "network_requests": 0}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
