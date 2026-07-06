#!/usr/bin/env python3
"""Build latest.json after verifying the exact immutable public snapshot commit."""
from __future__ import annotations

import argparse
import json
import subprocess
from datetime import date
from pathlib import Path
from typing import Any

from scripts.contract_common import SHA40_RE, load_object, require, safe_relative_path
from scripts.validate_market_artifact import require_git_commit, validate_market_artifact_at_commit


def _git_is_ancestor(repository_root: Path, ancestor: str, descendant: str) -> bool:
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", ancestor, descendant],
        cwd=repository_root,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return True
    if result.returncode == 1:
        return False
    raise ValueError("unable to verify commit ancestry")


def build_latest_pointer(
    *,
    repository_root: Path,
    snapshot_path: str,
    data_commit: str,
    public_commit: str,
    target_end_date: str,
    symbols_config: dict[str, Any],
    collection_config: dict[str, Any],
    expected_complete: bool | None = None,
    today: date | None = None,
) -> dict[str, Any]:
    require(bool(SHA40_RE.fullmatch(data_commit)), "data commit must be a full 40-character SHA")
    require(bool(SHA40_RE.fullmatch(public_commit)), "public commit must be a full 40-character SHA")
    require(data_commit != public_commit, "data and public commits must be different")
    require(target_end_date == "2026-07-24", "unexpected target end date")
    require(target_end_date == collection_config["target_end_date"], "target end date does not match collection contract")
    relative = safe_relative_path(snapshot_path, expected_prefix="snapshots")
    require(len(relative.parts) == 2, "snapshot path must be snapshots/<run-id>")
    require_git_commit(repository_root, data_commit)
    require_git_commit(repository_root, public_commit)
    require(_git_is_ancestor(repository_root, data_commit, public_commit), "public commit must descend from data commit")
    validation = validate_market_artifact_at_commit(
        repository_root=repository_root,
        public_commit=public_commit,
        snapshot_path=relative.as_posix(),
        expected_data_commit=data_commit,
        symbols_config=symbols_config,
        collection_config=collection_config,
        today=today,
    )
    derived_complete = bool(validation.receipt["target_window_complete"])
    if expected_complete is not None:
        require(expected_complete is derived_complete, "requested completion state does not match validated snapshot")
    return {
        "schema_version": "1.0.0",
        "snapshot_path": relative.as_posix(),
        "data_commit": data_commit,
        "public_commit": public_commit,
        "target_end_date": target_end_date,
        "target_window_complete": derived_complete,
    }


def write_latest_pointer(path: Path, pointer: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(pointer, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--snapshot-path", required=True)
    parser.add_argument("--data-commit", required=True)
    parser.add_argument("--public-commit", required=True)
    parser.add_argument("--target-end-date", default="2026-07-24")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--symbols-config", type=Path, default=Path("config/iteration_16_symbols.json"))
    parser.add_argument("--collection-config", type=Path, default=Path("config/iteration_16_collection.json"))
    parser.add_argument("--expect-complete", action="store_true")
    parser.add_argument("--today")
    args = parser.parse_args()
    try:
        pointer = build_latest_pointer(
            repository_root=args.repository_root,
            snapshot_path=args.snapshot_path,
            data_commit=args.data_commit,
            public_commit=args.public_commit,
            target_end_date=args.target_end_date,
            symbols_config=load_object(args.symbols_config),
            collection_config=load_object(args.collection_config),
            expected_complete=True if args.expect_complete else None,
            today=date.fromisoformat(args.today) if args.today else None,
        )
        write_latest_pointer(args.output, pointer)
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise SystemExit(f"latest pointer build failed: {exc}") from exc
    print(json.dumps(pointer, sort_keys=True))


if __name__ == "__main__":
    main()
