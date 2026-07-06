#!/usr/bin/env python3
"""Verify the exact three-commit market publication transaction before push."""
from __future__ import annotations

import argparse
import json
import subprocess
from datetime import date
from pathlib import Path
from typing import Any

from scripts.contract_common import SHA40_RE, load_object, require, safe_relative_path
from scripts.validate_latest_pointer import validate_latest_pointer
from scripts.validate_market_artifact import validate_market_artifact_at_commit


def _git(repository_root: Path, *args: str, binary: bool = False) -> str | bytes:
    result = subprocess.run(
        ["git", *args],
        cwd=repository_root,
        check=False,
        capture_output=True,
        text=not binary,
    )
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace") if binary else result.stderr
        raise ValueError(f"git {' '.join(args)} failed: {str(stderr).strip()}")
    return result.stdout


def _require_commit(repository_root: Path, commit: str, label: str) -> None:
    require(bool(SHA40_RE.fullmatch(commit)), f"{label} must be a full 40-character SHA")
    _git(repository_root, "cat-file", "-e", f"{commit}^{{commit}}")


def _parents(repository_root: Path, commit: str) -> list[str]:
    line = str(_git(repository_root, "rev-list", "--parents", "-n", "1", commit)).strip()
    parts = line.split()
    require(parts and parts[0] == commit, "unable to read commit parents")
    return parts[1:]


def _changed_paths(repository_root: Path, commit: str) -> list[str]:
    output = str(
        _git(
            repository_root,
            "diff-tree",
            "--root",
            "--no-commit-id",
            "--name-only",
            "-r",
            commit,
        )
    )
    return sorted(line for line in output.splitlines() if line)


def verify_publication_transaction(
    *,
    repository_root: Path,
    previous_head: str,
    data_commit: str,
    public_commit: str,
    pointer_commit: str,
    snapshot_path: str,
    latest_file: Path,
    symbols_config: dict[str, Any],
    collection_config: dict[str, Any],
    today: date | None = None,
) -> dict[str, Any]:
    repository_root = repository_root.resolve()
    relative = safe_relative_path(snapshot_path, expected_prefix="snapshots")
    require(len(relative.parts) == 2, "snapshot path must be snapshots/<run-id>")

    for label, commit in (
        ("previous head", previous_head),
        ("data commit", data_commit),
        ("public commit", public_commit),
        ("pointer commit", pointer_commit),
    ):
        _require_commit(repository_root, commit, label)

    require(
        _parents(repository_root, data_commit) == [previous_head],
        "data commit must directly descend from previous head",
    )
    require(
        _parents(repository_root, public_commit) == [data_commit],
        "public commit must directly descend from data commit",
    )
    require(
        _parents(repository_root, pointer_commit) == [public_commit],
        "pointer commit must directly descend from public commit",
    )

    expected_data_paths = sorted(
        (
            (relative / "market_prices.csv").as_posix(),
            (relative / "collection_receipt.json").as_posix(),
        )
    )
    require(
        _changed_paths(repository_root, data_commit) == expected_data_paths,
        "data commit changed unexpected files",
    )
    require(
        _changed_paths(repository_root, public_commit)
        == [(relative / "market_artifact_manifest.json").as_posix()],
        "public commit changed unexpected files",
    )
    require(
        _changed_paths(repository_root, pointer_commit) == ["latest.json"],
        "pointer commit changed unexpected files",
    )

    committed_latest = json.loads(str(_git(repository_root, "show", f"{pointer_commit}:latest.json")))
    local_latest = load_object(latest_file)
    require(committed_latest == local_latest, "working latest.json does not match pointer commit")
    validated_latest = validate_latest_pointer(latest_file, collection_config=collection_config)
    require(validated_latest["snapshot_path"] == relative.as_posix(), "latest pointer snapshot path mismatch")
    require(validated_latest["data_commit"] == data_commit, "latest pointer data commit mismatch")
    require(validated_latest["public_commit"] == public_commit, "latest pointer public commit mismatch")

    validation = validate_market_artifact_at_commit(
        repository_root=repository_root,
        public_commit=public_commit,
        snapshot_path=relative.as_posix(),
        expected_data_commit=data_commit,
        symbols_config=symbols_config,
        collection_config=collection_config,
        today=today,
    )
    require(
        bool(validation.receipt["target_window_complete"])
        is validated_latest["target_window_complete"],
        "latest pointer completion state mismatch",
    )

    return {
        "previous_head": previous_head,
        "data_commit": data_commit,
        "public_commit": public_commit,
        "pointer_commit": pointer_commit,
        "snapshot_path": relative.as_posix(),
        "row_count": validation.summary.row_count,
        "symbol_count": validation.summary.symbol_count,
        "target_window_complete": validated_latest["target_window_complete"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--previous-head", required=True)
    parser.add_argument("--data-commit", required=True)
    parser.add_argument("--public-commit", required=True)
    parser.add_argument("--pointer-commit", required=True)
    parser.add_argument("--snapshot-path", required=True)
    parser.add_argument("--latest-file", type=Path, required=True)
    parser.add_argument("--symbols-config", type=Path, default=Path("config/iteration_16_symbols.json"))
    parser.add_argument("--collection-config", type=Path, default=Path("config/iteration_16_collection.json"))
    parser.add_argument("--today")
    args = parser.parse_args()
    try:
        result = verify_publication_transaction(
            repository_root=args.repository_root,
            previous_head=args.previous_head,
            data_commit=args.data_commit,
            public_commit=args.public_commit,
            pointer_commit=args.pointer_commit,
            snapshot_path=args.snapshot_path,
            latest_file=args.latest_file,
            symbols_config=load_object(args.symbols_config),
            collection_config=load_object(args.collection_config),
            today=date.fromisoformat(args.today) if args.today else None,
        )
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise SystemExit(f"publication transaction validation failed: {exc}") from exc
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
