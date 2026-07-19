#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


IDENTITY_FIELDS = (
    "provider",
    "provider_article_id",
    "source_url",
    "source_hash",
    "published_at_utc",
    "ticker",
    "source_ticker",
    "source_type",
    "filing_type",
)
SHA256 = re.compile(r"[0-9a-f]{64}")
SHA1 = re.compile(r"[0-9a-f]{40}")


class CatalogError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CatalogError(message)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise CatalogError(f"invalid JSONL at {path}:{number}") from exc
        require(isinstance(value, dict), f"expected JSON object at {path}:{number}")
        records.append(value)
    require(bool(records), f"source record set is empty: {path}")
    return records


def canonical_identity(record: dict[str, Any]) -> dict[str, Any]:
    identity = {field: record.get(field) for field in IDENTITY_FIELDS}
    require(isinstance(identity["provider"], str) and bool(identity["provider"]), "record provider missing")
    require(
        isinstance(identity["source_hash"], str) and SHA256.fullmatch(identity["source_hash"]) is not None,
        "record source_hash invalid",
    )
    locator = identity["source_url"] or identity["provider_article_id"]
    require(isinstance(locator, str) and bool(locator), "record stable source locator missing")
    require(
        isinstance(identity["published_at_utc"], str) and bool(identity["published_at_utc"]),
        "record publication time missing",
    )
    require(isinstance(identity["ticker"], str) and bool(identity["ticker"]), "record ticker missing")
    return identity


def identity_key(record: dict[str, Any]) -> str:
    return json.dumps(canonical_identity(record), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def identity_keys(records: list[dict[str, Any]]) -> set[str]:
    keys = [identity_key(record) for record in records]
    require(len(keys) == len(set(keys)), "source records contain duplicate stable identities")
    return set(keys)


def source_fingerprint(keys: set[str]) -> str:
    require(bool(keys), "source identity set is empty")
    return hashlib.sha256(("\n".join(sorted(keys)) + "\n").encode("utf-8")).hexdigest()


def build_candidate_chain(
    *,
    baseline_records: list[dict[str, Any]],
    runs: list[dict[str, Any]],
    required_candidates: int = 2,
) -> dict[str, Any]:
    require(required_candidates > 0, "required candidate count must be positive")
    current_keys = identity_keys(baseline_records)
    current_fingerprint = source_fingerprint(current_keys)
    seen_fingerprints = {current_fingerprint}
    diagnostics: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []

    ordered = sorted(runs, key=lambda item: (str(item.get("created_at", "")), int(item.get("run_id", 0))))
    for run in ordered:
        run_id = int(run.get("run_id", 0))
        attempt = int(run.get("run_attempt", 0))
        head_sha = str(run.get("head_sha", "")).lower()
        artifact_name = str(run.get("artifact_name", ""))
        artifact_sha256 = str(run.get("artifact_sha256", "")).lower()
        records_path = Path(str(run.get("records_path", "")))
        require(run_id > 0 and attempt > 0, "invalid workflow run identity")
        require(SHA1.fullmatch(head_sha) is not None, f"invalid head SHA for run {run_id}")
        require(bool(artifact_name), f"artifact name missing for run {run_id}")
        require(SHA256.fullmatch(artifact_sha256) is not None, f"artifact digest invalid for run {run_id}")
        require(records_path.is_file(), f"records file missing for run {run_id}: {records_path}")

        keys = identity_keys(read_jsonl(records_path))
        fingerprint = source_fingerprint(keys)
        new_count = len(keys - current_keys)
        removed_count = len(current_keys - keys)
        unchanged_count = len(current_keys & keys)
        diagnostic = {
            "run_id": run_id,
            "run_attempt": attempt,
            "created_at": str(run.get("created_at", "")),
            "head_sha": head_sha,
            "artifact_name": artifact_name,
            "artifact_sha256": artifact_sha256,
            "source_content_sha256": fingerprint,
            "previous_source_content_sha256": current_fingerprint,
            "current_primary_record_count": len(keys),
            "new_primary_record_count": new_count,
            "removed_primary_record_count": removed_count,
            "unchanged_primary_record_count": unchanged_count,
            "eligible": new_count > 0 and fingerprint not in seen_fingerprints,
        }
        diagnostics.append(diagnostic)
        if not diagnostic["eligible"]:
            continue

        candidates.append(
            {
                **diagnostic,
                "sequence": 3 + len(candidates) + 1,
                "public_repository": "poudlesuman32-star/ai-market-news",
                "review_status": "catalogued_unreviewed_candidate",
                "publication_authorized": False,
                "registration_authorized": False,
                "later_stage_changes_enabled": False,
            }
        )
        current_keys = keys
        current_fingerprint = fingerprint
        seen_fingerprints.add(fingerprint)
        if len(candidates) == required_candidates:
            break

    return {
        "schema_version": "1.0.0",
        "contract_id": "PPI-R10-SOURCE-PERIOD-REGISTRY-001",
        "status": "candidate_chain_complete" if len(candidates) == required_candidates else "insufficient_novel_periods",
        "baseline_source_content_sha256": source_fingerprint(identity_keys(baseline_records)),
        "required_candidate_count": required_candidates,
        "candidate_count": len(candidates),
        "candidates": candidates,
        "diagnostics": diagnostics,
        "publication_authorized": False,
        "registration_authorized": False,
        "later_stage_changes_enabled": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Catalog genuinely novel R10 source-period candidates")
    parser.add_argument("--baseline-records", type=Path, required=True)
    parser.add_argument("--runs-manifest", type=Path, required=True)
    parser.add_argument("--required-candidates", type=int, default=2)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    manifest = json.loads(args.runs_manifest.read_text(encoding="utf-8"))
    require(isinstance(manifest, list), "runs manifest must be a list")
    result = build_candidate_chain(
        baseline_records=read_jsonl(args.baseline_records),
        runs=manifest,
        required_candidates=args.required_candidates,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
