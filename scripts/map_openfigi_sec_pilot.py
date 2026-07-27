from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

CONTRACT_ID = "PPI-OPENFIGI-MAPPING-PILOT-001-R1"
REVIEW_CONTRACT_ID = "PPI-SEC-UNIVERSE-ARTIFACT-REVIEW-001-R1"
SOURCE_CONTRACT_ID = "PPI-SEC-UNIVERSE-PILOT-001-R1"
REVIEW_WORKFLOW_NAME = "PPI SEC universe pilot artifact review"
EXPECTED_REPOSITORY = "poudlesuman32-star/ai-market-news"
ENDPOINT = "https://api.openfigi.com/v3/mapping"
HOST, PATH = "api.openfigi.com", "/v3/mapping"
REVIEW_PATHS = {"review.json", "review.md"}
SOURCE_PATHS = {"manifest.json", "receipt.json", "report.md", "sec-universe-pilot-500.jsonl"}
SUCCESS_PATHS = {"openfigi-mapping-500.jsonl", "manifest.json", "receipt.json", "report.md"}
BLOCKED_PATHS = {"blocked.json", "report.md"}
CANDIDATE_FIELDS = {
    "candidate_id", "cik", "company_name", "ticker", "exchange",
    "identity_status", "classification_status", "source_id", "source_row_sha256",
}
EXCHANGES = {"NYSE", "NASDAQ", "NYSE_AMERICAN"}
FIGI = re.compile(r"^[A-Z0-9]{12}$")
HEX64 = re.compile(r"^[a-f0-9]{64}$")
CID = re.compile(r"^ppi-sec-seed-[a-f0-9]{24}$")
TICKER = re.compile(r"^[A-Z0-9][A-Z0-9.\-]{0,14}$")
JOBS_PER_REQUEST = 10
EXPECTED_CANDIDATES = 500
EXPECTED_REQUESTS = 50
MIN_INTERVAL_SECONDS = 2.5
MAX_ATTEMPTS = 3
MAX_RESPONSE_BYTES = 5_000_000


class MappingError(RuntimeError):
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
        raise MappingError(f"Invalid JSON at {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise MappingError(f"{path} must contain one object")
    return value


def files_under(root: Path) -> set[str]:
    if not root.is_dir():
        raise MappingError(f"Artifact root is missing: {root}")
    paths = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}
    if any(p.startswith(".") or "/." in p for p in paths):
        raise MappingError("Hidden artifact paths are forbidden")
    return paths


def validate_run(value: dict, run_id: str, attempt: str, workflow_name: str) -> dict:
    if not run_id.isdigit() or not attempt.isdigit():
        raise MappingError("Run ID and attempt must be decimal integers")
    checks = {
        "id": value.get("id") == int(run_id),
        "attempt": value.get("run_attempt") == int(attempt),
        "name": value.get("name") == workflow_name,
        "repository": (value.get("repository") or {}).get("full_name") == EXPECTED_REPOSITORY,
        "main": value.get("head_branch") == "main",
        "completed": value.get("status") == "completed",
        "success": value.get("conclusion") == "success",
    }
    failed = [key for key, ok in checks.items() if not ok]
    if failed:
        raise MappingError("Run identity failed: " + ", ".join(failed))
    return checks


def validate_review(review_root: Path, review_run_json: Path, review_run_id: str,
                    review_run_attempt: str) -> dict:
    if files_under(review_root) != REVIEW_PATHS:
        raise MappingError("Review artifact paths are not exact")
    run_checks = validate_run(
        read_json(review_run_json), review_run_id, review_run_attempt, REVIEW_WORKFLOW_NAME
    )
    review = read_json(review_root / "review.json")
    review_core = {k: v for k, v in review.items() if k != "review_core_sha256"}
    checks = {
        "review_contract": review.get("review_contract_id") == REVIEW_CONTRACT_ID,
        "source_contract": review.get("source_contract_id") == SOURCE_CONTRACT_ID,
        "repository": review.get("source_repository") == EXPECTED_REPOSITORY,
        "review_hash": review.get("review_core_sha256") == digest(canon(review_core)),
        "candidate_count_type": isinstance(review.get("candidate_count"), int),
        "source_run_id_type": isinstance(review.get("source_run_id"), int),
        "source_run_attempt_type": isinstance(review.get("source_run_attempt"), int),
        "authority_openfigi_false": (review.get("authority") or {}).get("openfigi_mapping") is False,
        "no_private": (review.get("authority") or {}).get("private_access") is False,
        "no_deep": (review.get("authority") or {}).get("deep_evidence_collection") is False,
        "no_registry": (review.get("authority") or {}).get("registry_mutation") is False,
    }
    failed = [key for key, ok in checks.items() if not ok]
    if failed:
        raise MappingError("Review receipt failed: " + ", ".join(failed))
    return {**review, "review_run_checks": run_checks}


def write_github_output(path: str | None, values: dict[str, object]) -> None:
    if not path:
        return
    with Path(path).open("a", encoding="utf-8") as handle:
        for key, value in values.items():
            text = str(value).lower() if isinstance(value, bool) else str(value)
            if "\n" in text or "\r" in text:
                raise MappingError("GitHub output values must be single-line")
            handle.write(f"{key}={text}\n")


def write_blocked(root: Path, review: dict, reason: str) -> None:
    root.mkdir(parents=True, exist_ok=True)
    value = {
        "schema_version": "1.0.0",
        "contract_id": CONTRACT_ID,
        "status": "blocked",
        "reason": reason,
        "review_run_id": review.get("review_run_id"),
        "review_run_attempt": review.get("review_run_attempt"),
        "source_run_id": review.get("source_run_id"),
        "source_run_attempt": review.get("source_run_attempt"),
        "openfigi_requests_performed": 0,
        "private_access": False,
        "deep_evidence_collection": False,
        "registry_mutation": False,
        "generated_at_utc": now(),
    }
    (root / "blocked.json").write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    (root / "report.md").write_text(
        "# PPI OpenFIGI 500-candidate mapping pilot\n\n"
        "**Status:** blocked before OpenFIGI network access\n\n"
        f"Reason: {reason}\n"
    )
    if files_under(root) != BLOCKED_PATHS:
        raise MappingError("Blocked output paths are not exact")


def write_failure(root: Path, *, stage: str, message: str, review_run_id: str,
                  review_run_attempt: str) -> None:
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
        "review_run_id": review_run_id,
        "review_run_attempt": review_run_attempt,
        "openfigi_authorized_only_after_gate": True,
        "private_access": False,
        "deep_evidence_collection": False,
        "registry_mutation": False,
        "generated_at_utc": now(),
    }
    (root / "failure.json").write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    (root / "report.md").write_text(
        "# PPI OpenFIGI 500-candidate mapping pilot\n\n"
        "**Status:** failed closed\n\n"
        f"Stage: {stage}\n\nReason: {message}\n"
    )


def preflight(*, review_root: Path, review_run_json: Path, review_run_id: str,
              review_run_attempt: str, output_root: Path, github_output: str | None) -> dict:
    review = validate_review(review_root, review_run_json, review_run_id, review_run_attempt)
    passed = (
        review.get("gate_passed") is True
        and review.get("artifact_mode") == "success"
        and review.get("candidate_count") == EXPECTED_CANDIDATES
        and isinstance(review.get("snapshot_sha256"), str)
        and bool(HEX64.fullmatch(review["snapshot_sha256"]))
    )
    if not passed:
        reason = str(review.get("blocked_reason") or "SEC artifact review gate did not pass")
        write_blocked(output_root, {
            **review,
            "review_run_id": int(review_run_id),
            "review_run_attempt": int(review_run_attempt),
        }, reason)
    values = {
        "gate_passed": passed,
        "source_run_id": review.get("source_run_id", ""),
        "source_run_attempt": review.get("source_run_attempt", ""),
        "snapshot_sha256": review.get("snapshot_sha256", ""),
    }
    write_github_output(github_output, values)
    return values


def validate_candidate(value: object, index: int) -> dict:
    if not isinstance(value, dict) or set(value) != CANDIDATE_FIELDS:
        raise MappingError(f"Candidate {index} fields differ from the frozen schema")
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
    failed = [key for key, ok in checks.items() if not ok]
    if failed:
        raise MappingError(f"Candidate {index} failed: {', '.join(failed)}")
    return value


def validate_source_artifact(source_root: Path, review: dict) -> list[dict]:
    if files_under(source_root) != SOURCE_PATHS:
        raise MappingError("SEC source artifact paths are not exact")
    expected_hashes = review.get("artifact_file_sha256")
    if not isinstance(expected_hashes, dict) or set(expected_hashes) != SOURCE_PATHS:
        raise MappingError("Review receipt does not bind every SEC source artifact path")
    actual_hashes = {p: digest((source_root / p).read_bytes()) for p in sorted(SOURCE_PATHS)}
    if actual_hashes != expected_hashes:
        raise MappingError("SEC source artifact file hashes differ from the review receipt")

    snapshot = (source_root / "sec-universe-pilot-500.jsonl").read_bytes()
    if digest(snapshot) != review.get("snapshot_sha256"):
        raise MappingError("SEC snapshot hash differs from the review receipt")
    lines = snapshot.splitlines()
    if not snapshot.endswith(b"\n") or len(lines) != EXPECTED_CANDIDATES or any(not line.strip() for line in lines):
        raise MappingError("SEC snapshot must contain exactly 500 canonical JSONL records")
    candidates = []
    for index, line in enumerate(lines, 1):
        try:
            candidates.append(validate_candidate(json.loads(line), index))
        except json.JSONDecodeError as exc:
            raise MappingError(f"Candidate {index} is invalid JSON: {exc}") from exc
    ids = [candidate["candidate_id"] for candidate in candidates]
    if ids != sorted(ids) or len(set(ids)) != EXPECTED_CANDIDATES:
        raise MappingError("SEC candidates must be sorted and unique")

    manifest = read_json(source_root / "manifest.json")
    receipt = read_json(source_root / "receipt.json")
    checks = {
        "manifest_contract": manifest.get("contract_id") == SOURCE_CONTRACT_ID,
        "manifest_snapshot": manifest.get("snapshot_sha256") == review.get("snapshot_sha256"),
        "manifest_core": manifest.get("manifest_core_sha256") == review.get("manifest_core_sha256"),
        "receipt_contract": receipt.get("contract_id") == SOURCE_CONTRACT_ID,
        "receipt_snapshot": receipt.get("snapshot_sha256") == review.get("snapshot_sha256"),
        "receipt_run_id": str(receipt.get("run_id")) == str(review.get("source_run_id")),
        "receipt_run_attempt": str(receipt.get("run_attempt")) == str(review.get("source_run_attempt")),
        "raw_not_retained": receipt.get("raw_payload_retained") is False,
        "no_private": receipt.get("private_access") is False,
        "no_deep": receipt.get("deep_evidence") is False,
        "no_registry": receipt.get("registry_mutation") is False,
    }
    failed = [key for key, ok in checks.items() if not ok]
    if failed:
        raise MappingError("SEC source artifact failed: " + ", ".join(failed))
    return candidates


def request_job(candidate: dict) -> dict:
    return {
        "idType": "TICKER",
        "idValue": candidate["ticker"],
        "exchCode": "US",
        "marketSecDes": "Equity",
    }


def normalize_match(value: object) -> dict | None:
    if not isinstance(value, dict):
        return None
    figi = value.get("figi")
    ticker = value.get("ticker")
    if not isinstance(figi, str) or not FIGI.fullmatch(figi):
        return None
    if not isinstance(ticker, str) or not ticker.strip():
        return None

    def optional_figi(key: str) -> str | None:
        raw = value.get(key)
        return raw if isinstance(raw, str) and FIGI.fullmatch(raw) else None

    return {
        "figi": figi,
        "composite_figi": optional_figi("compositeFIGI"),
        "share_class_figi": optional_figi("shareClassFIGI"),
        "ticker": " ".join(ticker.upper().split()),
        "name": " ".join(str(value.get("name") or "").split()) or None,
        "exchange_code": " ".join(str(value.get("exchCode") or "").split()) or None,
        "market_sector": " ".join(str(value.get("marketSector") or "").split()) or None,
        "security_type": " ".join(str(value.get("securityType") or "").split()) or None,
        "security_type2": " ".join(str(value.get("securityType2") or "").split()) or None,
        "security_description": " ".join(str(value.get("securityDescription") or "").split()) or None,
    }


def classify_result(candidate: dict, result: object) -> dict:
    if not isinstance(result, dict):
        raise MappingError(f"OpenFIGI result for {candidate['candidate_id']} is not an object")
    if "error" in result:
        raise MappingError(f"OpenFIGI returned an error for {candidate['candidate_id']}: {result['error']}")
    response_hash = digest(canon(result))
    if "warning" in result:
        return {
            "candidate_id": candidate["candidate_id"],
            "cik": candidate["cik"],
            "ticker": candidate["ticker"],
            "exchange": candidate["exchange"],
            "source_row_sha256": candidate["source_row_sha256"],
            "mapping_status": "unmatched",
            "match_count": 0,
            "matches": [],
            "request_sha256": digest(canon(request_job(candidate))),
            "response_sha256": response_hash,
            "reason": "no_identifier_found",
        }
    data = result.get("data")
    if not isinstance(data, list):
        raise MappingError(f"OpenFIGI result for {candidate['candidate_id']} lacks data or warning")
    normalized = []
    for item in data:
        match = normalize_match(item)
        if match is None:
            continue
        if match["ticker"] != candidate["ticker"]:
            continue
        if match["market_sector"] != "Equity":
            continue
        normalized.append(match)
    deduped = {item["figi"]: item for item in normalized}
    matches = [deduped[key] for key in sorted(deduped)]
    if len(matches) == 1:
        status, reason = "exact", None
    elif len(matches) > 1:
        status, reason = "ambiguous", "multiple_eligible_figi_matches"
    else:
        status, reason = "unmatched", "no_eligible_equity_match"
    return {
        "candidate_id": candidate["candidate_id"],
        "cik": candidate["cik"],
        "ticker": candidate["ticker"],
        "exchange": candidate["exchange"],
        "source_row_sha256": candidate["source_row_sha256"],
        "mapping_status": status,
        "match_count": len(matches),
        "matches": matches,
        "request_sha256": digest(canon(request_job(candidate))),
        "response_sha256": response_hash,
        "reason": reason,
    }


class RedirectGuard(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[override]
        parsed = urllib.parse.urlparse(newurl)
        if (parsed.scheme, parsed.hostname, parsed.path) != ("https", HOST, PATH):
            raise MappingError(f"OpenFIGI redirect left the approved endpoint: {newurl}")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch_batch(jobs: list[dict], opener=None, sleep: Callable[[float], None] = time.sleep) -> list:
    if not 1 <= len(jobs) <= JOBS_PER_REQUEST:
        raise MappingError("OpenFIGI anonymous mapping requests must contain 1-10 jobs")
    parsed = urllib.parse.urlparse(ENDPOINT)
    if (parsed.scheme, parsed.hostname, parsed.path) != ("https", HOST, PATH):
        raise MappingError("OpenFIGI URL is outside the frozen allowlist")
    payload = json.dumps(jobs, sort_keys=True, separators=(",", ":")).encode()
    request = urllib.request.Request(
        ENDPOINT,
        data=payload,
        method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    opener = opener or urllib.request.build_opener(RedirectGuard())
    errors = []
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            with opener.open(request, timeout=30) as response:
                raw = response.read(MAX_RESPONSE_BYTES + 1)
                if len(raw) > MAX_RESPONSE_BYTES:
                    raise MappingError("OpenFIGI response exceeded the 5 MB per-request limit")
                if response.status != 200:
                    raise MappingError(f"OpenFIGI returned unexpected status {response.status}")
                try:
                    value = json.loads(raw)
                except json.JSONDecodeError as exc:
                    raise MappingError(f"OpenFIGI response is not valid JSON: {exc}") from exc
                if not isinstance(value, list) or len(value) != len(jobs):
                    raise MappingError("OpenFIGI response length differs from the request length")
                return value
        except urllib.error.HTTPError as exc:
            errors.append(f"attempt={attempt}:HTTP:{exc.code}")
            if exc.code not in {429, 500, 503} or attempt == MAX_ATTEMPTS:
                break
            reset = exc.headers.get("ratelimit-reset") if exc.headers else None
            delay = min(60.0, max(2.5, float(reset))) if reset and str(reset).replace(".", "", 1).isdigit() else 2.5 * attempt
            sleep(delay)
        except urllib.error.URLError as exc:
            errors.append(f"attempt={attempt}:URL:{exc.reason}")
            if attempt == MAX_ATTEMPTS:
                break
            sleep(2.5 * attempt)
    raise MappingError("OpenFIGI request failed after bounded retries: " + "; ".join(errors))


def map_candidates(candidates: list[dict], fetcher: Callable[[list[dict]], list] = fetch_batch,
                   sleep: Callable[[float], None] = time.sleep) -> tuple[list[dict], int]:
    if len(candidates) != EXPECTED_CANDIDATES:
        raise MappingError("Exactly 500 SEC candidates are required")
    outputs = []
    request_count = 0
    for start in range(0, len(candidates), JOBS_PER_REQUEST):
        batch_candidates = candidates[start:start + JOBS_PER_REQUEST]
        results = fetcher([request_job(candidate) for candidate in batch_candidates])
        if not isinstance(results, list) or len(results) != len(batch_candidates):
            raise MappingError("OpenFIGI batch result count differs from batch candidate count")
        outputs.extend(classify_result(candidate, result) for candidate, result in zip(batch_candidates, results))
        request_count += 1
        if start + JOBS_PER_REQUEST < len(candidates):
            sleep(MIN_INTERVAL_SECONDS)
    outputs.sort(key=lambda item: item["candidate_id"])
    if request_count != EXPECTED_REQUESTS or len(outputs) != EXPECTED_CANDIDATES:
        raise MappingError("OpenFIGI pilot did not produce the exact request and result counts")
    return outputs, request_count


def mapping_snapshot(records: list[dict]) -> bytes:
    return b"".join(canon(record) for record in records)


def write_outputs(root: Path, review: dict, records: list[dict], request_count: int,
                  contract_path: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    if any(root.iterdir()):
        raise MappingError("Mapping output root must be empty")
    snapshot = mapping_snapshot(records)
    counts = {state: sum(record["mapping_status"] == state for record in records)
              for state in ("exact", "ambiguous", "unmatched")}
    response_digest = digest(canon([record["response_sha256"] for record in records]))
    generated_at = now()
    core = {
        "schema_version": "1.0.0",
        "contract_id": CONTRACT_ID,
        "generated_at_utc": generated_at,
        "endpoint": ENDPOINT,
        "authentication_mode": "unauthenticated_free_tier",
        "api_key_used": False,
        "review_run_id": review["review_run_id"],
        "review_run_attempt": review["review_run_attempt"],
        "source_run_id": review["source_run_id"],
        "source_run_attempt": review["source_run_attempt"],
        "source_snapshot_sha256": review["snapshot_sha256"],
        "candidate_count": len(records),
        "jobs_per_request": JOBS_PER_REQUEST,
        "request_count": request_count,
        "mapping_counts": counts,
        "mapping_snapshot_sha256": digest(snapshot),
        "normalized_response_digest_sha256": response_digest,
        "raw_openfigi_responses_retained": False,
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
        "mapping_snapshot_sha256": manifest["mapping_snapshot_sha256"],
        "manifest_core_sha256": manifest["manifest_core_sha256"],
        "source_snapshot_sha256": review["snapshot_sha256"],
        "openfigi_requests_performed": request_count,
        "api_key_used": False,
        "raw_openfigi_responses_retained": False,
        "private_access": False,
        "screening": False,
        "deep_evidence_collection": False,
        "private_dispatch": False,
        "billing_budget_mutation": False,
        "registry_mutation": False,
        "production": False,
        "publication": False,
        "trading": False,
        "authorized_actions": ["openfigi_mapping_public_pilot"],
    }
    (root / "openfigi-mapping-500.jsonl").write_bytes(snapshot)
    (root / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    (root / "receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    (root / "report.md").write_text(
        "# PPI OpenFIGI 500-candidate mapping pilot\n\n"
        "- Status: success\n"
        f"- Candidates: {len(records)}\n"
        f"- Requests: {request_count}\n"
        f"- Exact: {counts['exact']}\n"
        f"- Ambiguous: {counts['ambiguous']}\n"
        f"- Unmatched: {counts['unmatched']}\n"
        "- API key used: no\n"
        "- Raw OpenFIGI responses retained: no\n"
        "- Private repository accessed: no\n"
        "- Screening or deep evidence performed: no\n"
    )
    if files_under(root) != SUCCESS_PATHS:
        raise MappingError("Success output paths are not exact")


def execute_mapping(*, review_root: Path, review_run_json: Path, review_run_id: str,
                    review_run_attempt: str, source_root: Path, output_root: Path,
                    contract_path: Path, fetcher: Callable[[list[dict]], list] = fetch_batch,
                    sleep: Callable[[float], None] = time.sleep) -> dict:
    review = validate_review(review_root, review_run_json, review_run_id, review_run_attempt)
    if not (
        review.get("gate_passed") is True
        and review.get("artifact_mode") == "success"
        and review.get("candidate_count") == EXPECTED_CANDIDATES
    ):
        raise MappingError("OpenFIGI mapping requires an exact passed SEC review receipt")
    candidates = validate_source_artifact(source_root, review)
    records, request_count = map_candidates(candidates, fetcher=fetcher, sleep=sleep)
    write_outputs(output_root, {
        **review,
        "review_run_id": int(review_run_id),
        "review_run_attempt": int(review_run_attempt),
    }, records, request_count, contract_path)
    return {"candidate_count": len(records), "request_count": request_count}


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

    run = sub.add_parser("map")
    run.add_argument("--review-root", type=Path, required=True)
    run.add_argument("--review-run-json", type=Path, required=True)
    run.add_argument("--review-run-id", required=True)
    run.add_argument("--review-run-attempt", required=True)
    run.add_argument("--source-root", type=Path, required=True)
    run.add_argument("--output-root", type=Path, required=True)
    run.add_argument("--contract", type=Path, default=Path("contracts/PPI-OPENFIGI-MAPPING-PILOT-001-R1.json"))

    args = parser.parse_args()
    if args.command == "preflight":
        try:
            preflight(
                review_root=args.review_root,
                review_run_json=args.review_run_json,
                review_run_id=args.review_run_id,
                review_run_attempt=args.review_run_attempt,
                output_root=args.output_root,
                github_output=args.github_output,
            )
            return 0
        except MappingError as exc:
            write_failure(
                args.output_root,
                stage="preflight",
                message=str(exc),
                review_run_id=args.review_run_id,
                review_run_attempt=args.review_run_attempt,
            )
            raise
    try:
        execute_mapping(
            review_root=args.review_root,
            review_run_json=args.review_run_json,
            review_run_id=args.review_run_id,
            review_run_attempt=args.review_run_attempt,
            source_root=args.source_root,
            output_root=args.output_root,
            contract_path=args.contract,
        )
        return 0
    except MappingError as exc:
        write_failure(
            args.output_root,
            stage="mapping",
            message=str(exc),
            review_run_id=args.review_run_id,
            review_run_attempt=args.review_run_attempt,
        )
        raise


if __name__ == "__main__":
    raise SystemExit(main())
