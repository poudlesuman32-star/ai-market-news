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


def content_fingerprint(keys: set[str]) -> str:
    payload = ("\n".join(sorted(keys)) + "\n").encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def assess_source_novelty(
    *,
    current_path: Path,
    previous_path: Path | None,
    minimum_new_records: int = 1,
) -> dict[str, Any]:
    require(minimum_new_records > 0, "minimum_new_records must be positive")
    current_records = read_jsonl(current_path)
    current_keys = {identity_key(record) for record in current_records}
    require(len(current_keys) == len(current_records), "current source records contain duplicate stable identities")

    if previous_path is None:
        previous_keys: set[str] = set()
        baseline_present = False
    else:
        previous_records = read_jsonl(previous_path)
        previous_keys = {identity_key(record) for record in previous_records}
        require(len(previous_keys) == len(previous_records), "previous source records contain duplicate stable identities")
        baseline_present = True

    new_keys = current_keys.difference(previous_keys)
    removed_keys = previous_keys.difference(current_keys)
    unchanged_keys = current_keys.intersection(previous_keys)
    materially_novel = not baseline_present or len(new_keys) >= minimum_new_records

    return {
        "schema_version": "1.0.0",
        "identity_fields": list(IDENTITY_FIELDS),
        "baseline_present": baseline_present,
        "current_record_count": len(current_keys),
        "previous_record_count": len(previous_keys),
        "new_record_count": len(new_keys),
        "removed_record_count": len(removed_keys),
        "unchanged_record_count": len(unchanged_keys),
        "minimum_new_records": minimum_new_records,
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
