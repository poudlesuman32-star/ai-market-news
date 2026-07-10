from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from .build_preview_artifacts import FORBIDDEN_PUBLIC_FIELDS, load_news
from .collector_common import CollectorError, require

SHA_RE = re.compile(r"^[a-f0-9]{40}$", re.IGNORECASE)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CollectorError(f"{path}: invalid JSON: {exc}") from exc
    require(isinstance(value, dict), f"{path}: expected a JSON object")
    return value


def build_news_manifest(
    *,
    news_path: Path,
    receipt_path: Path,
    snapshot_path: str,
    data_commit: str,
    source_repository: str,
) -> dict[str, Any]:
    require(source_repository == "poudlesuman32-star/ai-market-news", "unexpected source repository")
    require(SHA_RE.fullmatch(data_commit) is not None, "data_commit must be a 40-character SHA")
    require(snapshot_path.startswith("snapshots/") and ".." not in snapshot_path, "invalid snapshot_path")

    records = load_news(news_path)
    require(bool(records), "refusing to publish an empty public news dataset")
    receipt = load_json(receipt_path)
    require(receipt.get("collection_complete") is True, "collection receipt is incomplete")
    require(receipt.get("synthetic_content_used") is False, "receipt reports synthetic content")
    require(receipt.get("source_content_modified") is False, "receipt reports modified source content")
    require(receipt.get("private_content_excluded") is True, "receipt does not confirm private-content exclusion")
    require(not (FORBIDDEN_PUBLIC_FIELDS & set(receipt)), "receipt contains forbidden private fields")

    dataset_hash = sha256_file(news_path)
    require(receipt.get("dataset_sha256") == dataset_hash, "receipt dataset hash mismatch")
    require(receipt.get("record_count") == len(records), "receipt record count mismatch")

    providers = Counter(str(record["provider"]) for record in records)
    tickers = {str(record["ticker"]) for record in records}
    events = {str(record["event_id"]) for record in records}
    published = sorted(str(record["published_at_utc"]) for record in records)
    manifest = {
        "schema_version": "1.0.0",
        "source_repository": source_repository,
        "data_commit": data_commit,
        "snapshot_path": snapshot_path,
        "news_file_path": f"{snapshot_path}/news.jsonl",
        "news_file_sha256": dataset_hash,
        "receipt_file_path": f"{snapshot_path}/collection_receipt.json",
        "receipt_file_sha256": sha256_file(receipt_path),
        "record_count": len(records),
        "event_count": len(events),
        "ticker_count": len(tickers),
        "provider_counts": dict(sorted(providers.items())),
        "earliest_published_at": published[0],
        "latest_published_at": published[-1],
        "collection_complete": True,
        "synthetic_content_used": False,
        "source_content_modified": False,
        "private_content_excluded": True,
    }
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build an immutable public-news manifest")
    parser.add_argument("--news", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--snapshot-path", required=True)
    parser.add_argument("--data-commit", required=True)
    parser.add_argument("--source-repository", default="poudlesuman32-star/ai-market-news")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    manifest = build_news_manifest(
        news_path=args.news,
        receipt_path=args.receipt,
        snapshot_path=args.snapshot_path,
        data_commit=args.data_commit,
        source_repository=args.source_repository,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
