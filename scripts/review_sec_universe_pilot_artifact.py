from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

REVIEW_CONTRACT_ID = "PPI-SEC-UNIVERSE-ARTIFACT-REVIEW-001-R1"
SOURCE_CONTRACT_ID = "PPI-SEC-UNIVERSE-PILOT-001-R1"
SOURCE_WORKFLOW_NAME = "PPI SEC 500-instrument universe pilot"
SOURCE_WORKFLOW_PATH = ".github/workflows/ppi-sec-universe-pilot.yml"
SOURCE_EVENT = "workflow_dispatch"
SOURCE_URL = "https://www.sec.gov/files/company_tickers_exchange.json"
EXPECTED_REPOSITORY = "poudlesuman32-star/ai-market-news"
SUCCESS_PATHS = {"manifest.json", "receipt.json", "report.md", "sec-universe-pilot-500.jsonl"}
BLOCKED_PATHS = {"blocked.json", "report.md"}
FIELDS = {
    "candidate_id", "cik", "company_name", "ticker", "exchange",
    "identity_status", "classification_status", "source_id", "source_row_sha256",
}
EXCHANGES = {"NYSE", "NASDAQ", "NYSE_AMERICAN"}
HEX64 = re.compile(r"^[a-f0-9]{64}$")
CID = re.compile(r"^ppi-sec-seed-[a-f0-9]{24}$")
TICKER = re.compile(r"^[A-Z0-9][A-Z0-9.\-]{0,14}$")


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
    paths = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}
    if any(p.startswith(".") or "/." in p for p in paths):
        raise ReviewError("Hidden artifact paths are forbidden")
    return paths


def validate_source_run(value: dict, run_id: str, attempt: str) -> dict:
    if not run_id.isdigit() or not attempt.isdigit():
        raise ReviewError("Source run ID and attempt must be decimal integers")
    checks = {
        "id": value.get("id") == int(run_id),
        "attempt": value.get("run_attempt") == int(attempt),
        "workflow_path": value.get("path") == SOURCE_WORKFLOW_PATH,
        "event": value.get("event") == SOURCE_EVENT,
        "repository": (value.get("repository") or {}).get("full_name") == EXPECTED_REPOSITORY,
        "main": value.get("head_branch") == "main",
        "completed": value.get("status") == "completed",
        "success": value.get("conclusion") == "success",
    }
    failed = [k for k, ok in checks.items() if not ok]
    if failed:
        raise ReviewError("Source run identity failed: " + ", ".join(failed))
    return checks


def validate_blocked(root: Path) -> dict:
    value = read_json(root / "blocked.json")
    checks = {
        "contract": value.get("contract_id") == SOURCE_CONTRACT_ID,
        "status": value.get("status") == "blocked",
        "no_fetch": value.get("remote_fetch_performed") is False,
        "no_private": value.get("private_access") is False,
        "no_deep": value.get("deep_evidence") is False,
        "no_registry": value.get("registry_mutation") is False,
    }
    failed = [k for k, ok in checks.items() if not ok]
    if failed:
        raise ReviewError("Blocked artifact failed: " + ", ".join(failed))
    return {
        "artifact_mode": "blocked",
        "gate_passed": False,
        "candidate_count": 0,
        "blocked_reason": str(value.get("reason") or "unspecified"),
        "checks": checks,
    }


def validate_candidate(value: object, index: int) -> dict:
    if not isinstance(value, dict) or set(value) != FIELDS:
        raise ReviewError(f"Candidate {index} fields differ from the frozen schema")
    checks = {
        "candidate_id": isinstance(value["candidate_id"], str) and bool(CID.fullmatch(value["candidate_id"])),
        "cik": isinstance(value["cik"], str) and len(value["cik"]) == 10 and value["cik"].isdigit(),
        "company_name": isinstance(value["company_name"], str) and bool(value["company_name"].strip()),
        "ticker": isinstance(value["ticker"], str) and bool(TICKER.fullmatch(value["ticker"])),
        "exchange": value["exchange"] in EXCHANGES,
        "identity": value["identity_status"] == "provisional_sec_seed",
        "classification": value["classification_status"] == "unresolved",
        "source": value["source_id"] == "sec_company_tickers_exchange",
        "row_hash": isinstance(value["source_row_sha256"], str) and bool(HEX64.fullmatch(value["source_row_sha256"])),
    }
    failed = [k for k, ok in checks.items() if not ok]
    if failed:
        raise ReviewError(f"Candidate {index} failed: {', '.join(failed)}")
    return value


def validate_success(root: Path, contract_path: Path) -> dict:
    snapshot = (root / "sec-universe-pilot-500.jsonl").read_bytes()
    lines = snapshot.splitlines()
    if not snapshot.endswith(b"\n") or len(lines) != 500 or any(not line.strip() for line in lines):
        raise ReviewError("Snapshot must be canonical JSONL with exactly 500 non-empty lines")
    candidates = []
    for index, line in enumerate(lines, 1):
        try:
            candidates.append(validate_candidate(json.loads(line), index))
        except json.JSONDecodeError as exc:
            raise ReviewError(f"Candidate {index} is invalid JSON: {exc}") from exc
    ids = [v["candidate_id"] for v in candidates]
    keys = [(v["cik"], v["ticker"], v["exchange"]) for v in candidates]
    if ids != sorted(ids) or len(set(ids)) != 500 or len(set(keys)) != 500:
        raise ReviewError("Candidates must be sorted and unique")

    snapshot_hash = digest(snapshot)
    manifest = read_json(root / "manifest.json")
    core = {k: v for k, v in manifest.items() if k != "manifest_core_sha256"}
    checks = {
        "manifest_contract": manifest.get("contract_id") == SOURCE_CONTRACT_ID,
        "source_url": manifest.get("source_url") == SOURCE_URL,
        "candidate_count": manifest.get("candidate_count") == 500,
        "candidate_limit": manifest.get("candidate_limit") == 500,
        "selection": manifest.get("selection_algorithm") == "sha256_rank_v1",
        "snapshot_hash": manifest.get("snapshot_sha256") == snapshot_hash,
        "source_hash": isinstance(manifest.get("source_payload_sha256"), str) and bool(HEX64.fullmatch(manifest["source_payload_sha256"])),
        "manifest_hash": manifest.get("manifest_core_sha256") == digest(canon(core)),
        "source_rows": isinstance(manifest.get("source_row_count"), int) and manifest["source_row_count"] >= 500,
        "normalized_rows": isinstance(manifest.get("normalized_eligible_count"), int) and manifest["normalized_eligible_count"] >= 500,
    }
    receipt = read_json(root / "receipt.json")
    report = (root / "report.md").read_text(encoding="utf-8")
    checks.update({
        "receipt_contract": receipt.get("contract_id") == SOURCE_CONTRACT_ID,
        "contract_hash": receipt.get("contract_sha256") == digest(contract_path.read_bytes()),
        "receipt_snapshot": receipt.get("snapshot_sha256") == snapshot_hash,
        "receipt_source": receipt.get("source_payload_sha256") == manifest.get("source_payload_sha256"),
        "receipt_manifest": receipt.get("manifest_core_sha256") == manifest.get("manifest_core_sha256"),
        "remote_fetch": receipt.get("remote_fetch_performed") is True,
        "raw_not_retained": receipt.get("raw_payload_retained") is False,
        "no_private": receipt.get("private_access") is False,
        "no_deep": receipt.get("deep_evidence") is False,
        "no_registry": receipt.get("registry_mutation") is False,
        "no_extra_authority": receipt.get("authorized_actions") == [],
        "report": "Status: success" in report and "Candidate count: 500" in report,
    })
    failed = [k for k, ok in checks.items() if not ok]
    if failed:
        raise ReviewError("Success artifact failed: " + ", ".join(failed))
    return {
        "artifact_mode": "success",
        "gate_passed": True,
        "candidate_count": 500,
        "source_payload_sha256": manifest["source_payload_sha256"],
        "snapshot_sha256": snapshot_hash,
        "manifest_core_sha256": manifest["manifest_core_sha256"],
        "artifact_file_sha256": {p: digest((root / p).read_bytes()) for p in sorted(SUCCESS_PATHS)},
        "exclusion_counts": manifest.get("exclusion_counts", {}),
        "checks": checks,
    }


def review_artifact(*, artifact_root: Path, source_run_json: Path, source_run_id: str,
                    source_run_attempt: str, contract_path: Path) -> dict:
    source_checks = validate_source_run(read_json(source_run_json), source_run_id, source_run_attempt)
    paths = files_under(artifact_root)
    if paths == BLOCKED_PATHS:
        result = validate_blocked(artifact_root)
    elif paths == SUCCESS_PATHS:
        result = validate_success(artifact_root, contract_path)
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
            "openfigi_mapping": False,
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
    output = {**value, "review_core_sha256": digest(canon(value))}
    (root / "review.json").write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    status = "passed" if value.get("gate_passed") else "blocked"
    lines = [
        "# PPI SEC universe artifact review", "", f"- Status: {status}",
        f"- Source run: {value.get('source_run_id')} attempt {value.get('source_run_attempt')}",
        f"- Artifact mode: {value.get('artifact_mode')}",
        f"- Gate passed: {'yes' if value.get('gate_passed') else 'no'}",
        f"- Candidate count: {value.get('candidate_count', 0)}",
        "- OpenFIGI mapping performed: no", "- Private repository accessed: no",
        "- Screening or deep evidence performed: no",
    ]
    if value.get("blocked_reason"):
        lines.append(f"- Blocked reason: {value['blocked_reason']}")
    if value.get("snapshot_sha256"):
        lines.append(f"- Snapshot SHA-256: `{value['snapshot_sha256']}`")
    (root / "review.md").write_text("\n".join(lines) + "\n")


def write_failure(root: Path, message: str, run_id: str, attempt: str) -> None:
    root.mkdir(parents=True, exist_ok=True)
    value = {
        "schema_version": "1.0.0", "review_contract_id": REVIEW_CONTRACT_ID,
        "status": "failed", "gate_passed": False, "source_run_id": run_id,
        "source_run_attempt": attempt, "reviewed_at_utc": now(), "error": message,
        "authority": {"openfigi_mapping": False, "screening": False,
                      "deep_evidence_collection": False, "private_access": False,
                      "private_dispatch": False, "billing_budget_mutation": False,
                      "registry_mutation": False, "production": False,
                      "publication": False, "trading": False},
    }
    (root / "review.json").write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    (root / "review.md").write_text(f"# PPI SEC universe artifact review\n\n**Status:** failed closed\n\nReason: {message}\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--source-run-json", type=Path, required=True)
    parser.add_argument("--source-run-id", required=True)
    parser.add_argument("--source-run-attempt", required=True)
    parser.add_argument("--contract", type=Path, default=Path("contracts/PPI-SEC-UNIVERSE-PILOT-001-R1.json"))
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    try:
        value = review_artifact(artifact_root=args.artifact_root,
                                source_run_json=args.source_run_json,
                                source_run_id=args.source_run_id,
                                source_run_attempt=args.source_run_attempt,
                                contract_path=args.contract)
        write_review(args.output_root, value)
        return 0
    except ReviewError as exc:
        write_failure(args.output_root, str(exc), args.source_run_id, args.source_run_attempt)
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
