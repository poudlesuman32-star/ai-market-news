from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from .collector_common import CollectorError, require

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


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise CollectorError(f"cannot read source records: {path}") from exc
    records: list[dict[str, Any]] = []
    for number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise CollectorError(f"invalid JSONL record at {path}:{number}") from exc
        require(isinstance(value, dict), f"expected JSON object at {path}:{number}")
        records.append(value)
    require(bool(records), f"source record set is empty: {path}")
    return records


def stable_identity(record: dict[str, Any]) -> dict[str, Any]:
    identity = {field: record.get(field) for field in IDENTITY_FIELDS}
    require(isinstance(identity["provider"], str) and identity["provider"], "record provider missing")
    require(isinstance(identity["source_hash"], str) and len(identity["source_hash"]) == 64, "record source_hash missing")
    require(
        isinstance(identity["source_url"], str) and identity["source_url"]
        or isinstance(identity["provider_article_id"], str) and identity["provider_article_id"],
        "record stable source locator missing",
    )
    require(isinstance(identity["published_at_utc"], str) and identity["published_at_utc"], "record publication time missing")
    require(isinstance(identity["ticker"], str) and identity["ticker"], "record ticker missing")
    return identity


def identity_key(record: dict[str, Any]) -> str:
    return json.dumps(stable_identity(record), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def records_by_identity(records: list[dict[str, Any]], *, label: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for record in records:
        key = identity_key(record)
        require(key not in result, f"{label} source records contain duplicate stable identities")
        result[key] = record
    return result


def content_fingerprint(keys: set[str]) -> str:
    payload = ("\n".join(sorted(keys)) + "\n").encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def identity_breakdown(
    records: dict[str, dict[str, Any]],
    keys: set[str],
) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str, str | None], dict[str, Any]] = {}
    for key in sorted(keys):
        record = records[key]
        provider = str(record.get("provider", "")).strip()
        ticker = str(record.get("ticker", "")).strip().upper()
        source_type = str(record.get("source_type", "")).strip()
        raw_filing_type = record.get("filing_type")
        filing_type = str(raw_filing_type).strip() if raw_filing_type is not None else None
        published_at = str(record.get("published_at_utc", "")).strip()
        require(bool(provider and ticker and source_type and published_at), "source record breakdown fields missing")
        group_key = (provider, ticker, source_type, filing_type)
        group = groups.setdefault(
            group_key,
            {
                "provider": provider,
                "ticker": ticker,
                "source_type": source_type,
                "filing_type": filing_type,
                "record_count": 0,
                "latest_published_at_utc": published_at,
            },
        )
        group["record_count"] += 1
        if published_at > group["latest_published_at_utc"]:
            group["latest_published_at_utc"] = published_at
    return sorted(
        groups.values(),
        key=lambda value: (
            value["provider"],
            value["ticker"],
            value["source_type"],
            value["filing_type"] or "",
        ),
    )


def novelty_disposition(
    *,
    baseline_present: bool,
    new_count: int,
    removed_count: int,
    minimum_new_records: int,
) -> str:
    if not baseline_present:
        return "baseline_established"
    if new_count >= minimum_new_records:
        return "novel_stable_identities"
    if new_count > 0:
        return "insufficient_new_stable_identities"
    if removed_count > 0:
        return "removal_only"
    return "duplicate_identity_set"


def assess_source_novelty(
    *,
    current_path: Path,
    previous_path: Path | None,
    minimum_new_records: int = 1,
) -> dict[str, Any]:
    require(minimum_new_records > 0, "minimum_new_records must be positive")
    current_records = records_by_identity(read_jsonl(current_path), label="current")
    current_keys = set(current_records)

    if previous_path is None:
        previous_records: dict[str, dict[str, Any]] = {}
        previous_keys: set[str] = set()
        baseline_present = False
    else:
        previous_records = records_by_identity(read_jsonl(previous_path), label="previous")
        previous_keys = set(previous_records)
        baseline_present = True

    new_keys = current_keys.difference(previous_keys)
    removed_keys = previous_keys.difference(current_keys)
    unchanged_keys = current_keys.intersection(previous_keys)
    materially_novel = not baseline_present or len(new_keys) >= minimum_new_records

    return {
        "schema_version": "1.1.0",
        "identity_fields": list(IDENTITY_FIELDS),
        "baseline_present": baseline_present,
        "current_record_count": len(current_keys),
        "previous_record_count": len(previous_keys),
        "new_record_count": len(new_keys),
        "removed_record_count": len(removed_keys),
        "unchanged_record_count": len(unchanged_keys),
        "minimum_new_records": minimum_new_records,
        "novelty_disposition": novelty_disposition(
            baseline_present=baseline_present,
            new_count=len(new_keys),
            removed_count=len(removed_keys),
            minimum_new_records=minimum_new_records,
        ),
        "current_identity_breakdown": identity_breakdown(current_records, current_keys),
        "new_identity_breakdown": identity_breakdown(current_records, new_keys),
        "removed_identity_breakdown": identity_breakdown(previous_records, removed_keys),
        "unchanged_identity_breakdown": identity_breakdown(current_records, unchanged_keys),
        "source_content_sha256": content_fingerprint(current_keys),
        "previous_source_content_sha256": content_fingerprint(previous_keys) if baseline_present else None,
        "materially_novel": materially_novel,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Assess timestamp-independent material source novelty")
    parser.add_argument("--current", type=Path, required=True)
    parser.add_argument("--previous", type=Path)
    parser.add_argument("--minimum-new-records", type=int, default=1)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--report-only",
        action="store_true",
        help="Write a source-period receipt without requiring material novelty",
    )
    args = parser.parse_args(argv)

    result = assess_source_novelty(
        current_path=args.current,
        previous_path=args.previous,
        minimum_new_records=args.minimum_new_records,
    )
    result["report_only"] = args.report_only
    result["registration_authorized"] = False
    result["publication_authorized"] = False
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not args.report_only:
        require(result["materially_novel"] is True, "candidate adds no materially new source records")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
