from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from .collector_common import CollectorError, require

CONTRACT_ID = "PPI-R9-PUBLIC-INPUT-001"
CONTRACT_SHA256 = "cf2d19d7a4a05f3e6e0b7d847659cf4f6f4798a789e645dd8c2d06eae8c171c9"
VALIDATOR_VERSION = "public-input-contract-binding-v1"


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CollectorError(f"cannot read valid JSON: {path}") from exc
    require(isinstance(value, dict), f"expected JSON object: {path}")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind_public_input_contract(
    *,
    news_path: Path,
    receipt_path: Path,
    manifest_path: Path,
    report_path: Path,
    independent_path: Path,
) -> dict[str, Any]:
    receipt = _read_json(receipt_path)
    manifest = _read_json(manifest_path)
    report = _read_json(report_path)
    independent = _read_json(independent_path)

    request_counts = receipt.get("request_counts", {})
    provider_counts = receipt.get("provider_counts", {})
    checks = {
        "contract_identity_frozen": bool(CONTRACT_ID) and len(CONTRACT_SHA256) == 64,
        "candidate_only": receipt.get("candidate_only") is True and manifest.get("candidate_only") is True and report.get("candidate_only") is True,
        "read_only_no_publication": report.get("publication_enabled") is False and report.get("contents_write_permission_authorized") is False and report.get("external_writes_enabled") is False and report.get("published_to_repository") is False,
        "mixed_provider_requests_observed": int(request_counts.get("sec", 0)) > 0 and int(request_counts.get("official_company_sources", 0)) > 0,
        "accepted_sec_record_present": int(provider_counts.get("sec_edgar", 0)) > 0,
        "accepted_official_company_record_present": int(provider_counts.get("official_company_source", 0)) > 0,
        "provider_failures_fail_closed": receipt.get("provider_failures") == [] and report.get("provider_failures") == [],
        "independent_validator_passed": independent.get("candidate_valid") is True and independent.get("failures") == [],
        "manual_authorization_absent": independent.get("publication_authorized") is False and independent.get("official_r9_count_authorized") is False,
        "exact_news_hash_recomputed": receipt.get("dataset_sha256") == manifest.get("file_sha256") == _sha256(news_path),
    }
    failures = sorted(name for name, passed in checks.items() if not passed)
    status = "candidate_ready_for_manual_authorization" if not failures else "validation_failed"
    return {
        "schema_version": "1.0.0",
        "validator_version": VALIDATOR_VERSION,
        "contract_id": CONTRACT_ID,
        "contract_sha256": CONTRACT_SHA256,
        "status": status,
        "checks": checks,
        "failures": failures,
        "blocked_external": [] if failures else ["manual_approval_required"],
        "input_sha256": {
            "news.jsonl": _sha256(news_path),
            "collection_receipt.json": _sha256(receipt_path),
            "news_manifest.preview.json": _sha256(manifest_path),
            "run_report.json": _sha256(report_path),
            "independent_validation.json": _sha256(independent_path),
        },
        "publication_authorized": False,
        "official_r9_count_authorized": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bind a live candidate to the frozen R9 public-input validation contract")
    parser.add_argument("--news", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--independent", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    result = bind_public_input_contract(
        news_path=args.news,
        receipt_path=args.receipt,
        manifest_path=args.manifest,
        report_path=args.report,
        independent_path=args.independent,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    if result["status"] == "validation_failed":
        raise CollectorError("public-input contract binding failed: " + ", ".join(result["failures"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
