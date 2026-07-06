#!/usr/bin/env python3
"""Build a deterministic manifest from a validated Iteration 16 market CSV."""
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any

from scripts.contract_common import SHA40_RE, load_object, market_artifact_id, require, safe_relative_path, sha256
from scripts.validate_market_csv import validate_market_csv


def build_market_manifest(
    *,
    data_file: Path,
    data_file_path: str,
    provider_name: str,
    source_repository: str,
    source_commit_sha: str,
    symbols_config: dict[str, Any],
    collection_config: dict[str, Any],
    notes: str | None = None,
    today: date | None = None,
) -> dict[str, Any]:
    require(str(provider_name).strip() != "", "provider name is required")
    require(source_repository == collection_config["source_repository"], "unexpected source repository")
    require(bool(SHA40_RE.fullmatch(source_commit_sha)), "source commit SHA must be 40 lowercase hex characters")
    relative_path = safe_relative_path(data_file_path, expected_prefix="snapshots")
    require(relative_path.name == "market_prices.csv", "data file path must end with market_prices.csv")
    require(data_file.is_file(), "market CSV does not exist")
    summary = validate_market_csv(
        data_file,
        symbols_config=symbols_config,
        collection_config=collection_config,
        today=today,
    )
    digest = sha256(data_file)
    return {
        "manifest_version": "1.0.0",
        "contract_id": collection_config["contract_id"],
        "artifact_id": market_artifact_id(
            source_repository=source_repository,
            source_commit_sha=source_commit_sha,
            data_file_path=relative_path.as_posix(),
            data_file_sha256=digest,
        ),
        "provider_name": provider_name.strip(),
        "source_repository": source_repository,
        "source_commit_sha": source_commit_sha,
        "data_file_path": relative_path.as_posix(),
        "data_file_sha256": digest,
        "data_format": "csv",
        "encoding": "utf-8",
        "calendar": collection_config["calendar"],
        "timezone": collection_config["timezone"],
        "corporate_action_adjusted": True,
        "regular_session_only": True,
        "symbol_count": summary.symbol_count,
        "row_count": summary.row_count,
        "symbols": list(summary.symbols),
        "start_date": summary.start_date,
        "end_date": summary.end_date,
        "source_data_modified": False,
        "synthetic_prices_used": False,
        "notes": notes,
    }


def write_manifest(path: Path, manifest: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-file", type=Path, required=True)
    parser.add_argument("--data-file-path", required=True)
    parser.add_argument("--provider-name", required=True)
    parser.add_argument("--source-repository", required=True)
    parser.add_argument("--source-commit-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--symbols-config", type=Path, default=Path("config/iteration_16_symbols.json"))
    parser.add_argument("--collection-config", type=Path, default=Path("config/iteration_16_collection.json"))
    parser.add_argument("--notes")
    parser.add_argument("--today")
    args = parser.parse_args()
    try:
        manifest = build_market_manifest(
            data_file=args.data_file,
            data_file_path=args.data_file_path,
            provider_name=args.provider_name,
            source_repository=args.source_repository,
            source_commit_sha=args.source_commit_sha,
            symbols_config=load_object(args.symbols_config),
            collection_config=load_object(args.collection_config),
            notes=args.notes,
            today=date.fromisoformat(args.today) if args.today else None,
        )
        write_manifest(args.output, manifest)
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise SystemExit(f"market manifest build failed: {exc}") from exc
    print(json.dumps(manifest, sort_keys=True))


if __name__ == "__main__":
    main()
