#!/usr/bin/env python3
"""Validate an immutable Iteration 16 snapshot on disk or at an exact Git commit."""
from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from scripts.contract_common import SHA40_RE, CsvSummary, load_object, parse_date, require, safe_relative_path, sha256
from scripts.validate_market_manifest import validate_market_manifest

REQUIRED_SNAPSHOT_FILES = (
    "market_prices.csv",
    "collection_receipt.json",
    "market_artifact_manifest.json",
)
RECEIPT_FIELDS = {
    "receipt_version", "iteration", "contract_id", "provider_name", "provider_host",
    "collected_at_utc", "requested_start_date", "requested_end_date", "actual_start_date",
    "actual_end_date", "actual_end_date_all_symbols", "target_end_date", "target_window_complete",
    "required_symbols", "row_count", "symbol_count", "request_count", "per_symbol",
    "adjustment_method", "corporate_action_adjusted", "regular_session_only",
    "synthetic_prices_used", "source_data_modified", "csv_sha256", "validated_row_count",
}


@dataclass(frozen=True)
class ArtifactValidation:
    snapshot_path: str
    manifest: dict[str, Any]
    receipt: dict[str, Any]
    summary: CsvSummary


def _snapshot_relative_path(value: str) -> Path:
    path = safe_relative_path(value, expected_prefix="snapshots")
    require(len(path.parts) == 2, "snapshot path must be snapshots/<run-id>")
    require(path.parts[1] not in ("", "."), "snapshot run id is required")
    return path


def _fingerprint(path: Path) -> tuple[int, int, int, int, str]:
    stat = path.stat()
    return (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, sha256(path))


def _parse_utc_timestamp(value: Any) -> None:
    text = str(value)
    require(text.endswith("Z"), "collected_at_utc must use UTC Z notation")
    try:
        datetime.fromisoformat(text[:-1] + "+00:00")
    except ValueError as exc:
        raise ValueError("invalid collected_at_utc") from exc


def validate_market_artifact(
    *,
    repository_root: Path,
    snapshot_path: str,
    expected_data_commit: str,
    symbols_config: dict[str, Any],
    collection_config: dict[str, Any],
    today: date | None = None,
) -> ArtifactValidation:
    require(bool(SHA40_RE.fullmatch(expected_data_commit)), "expected data commit must be a full 40-character SHA")
    relative = _snapshot_relative_path(snapshot_path)
    root = repository_root.resolve()
    snapshot = (root / relative).resolve()
    require(snapshot.is_relative_to(root), "snapshot path escapes repository root")
    require(snapshot.is_dir(), "snapshot directory does not exist")
    require(not snapshot.is_symlink(), "snapshot directory may not be a symlink")
    entries = sorted(item.name for item in snapshot.iterdir())
    require(entries == sorted(REQUIRED_SNAPSHOT_FILES), "snapshot must contain exactly the three required files")

    paths = {name: snapshot / name for name in REQUIRED_SNAPSHOT_FILES}
    for name, path in paths.items():
        require(path.is_file(), f"missing snapshot file: {name}")
        require(not path.is_symlink(), f"snapshot file may not be a symlink: {name}")
    before = {name: _fingerprint(path) for name, path in paths.items()}

    manifest_path = paths["market_artifact_manifest.json"]
    receipt_path = paths["collection_receipt.json"]
    summary = validate_market_manifest(
        manifest_path,
        market_root=root,
        symbols_config=symbols_config,
        collection_config=collection_config,
        today=today,
    )
    manifest = load_object(manifest_path)
    receipt = load_object(receipt_path)
    expected_csv_path = (relative / "market_prices.csv").as_posix()
    require(manifest["data_file_path"] == expected_csv_path, "manifest CSV path does not match snapshot path")
    require(manifest["source_commit_sha"] == expected_data_commit, "manifest data commit does not match expected data commit")

    require(set(receipt) == RECEIPT_FIELDS, "collection receipt fields do not match the contract")
    require(receipt["receipt_version"] == "1.0.0", "unexpected receipt version")
    require(receipt["iteration"] == 16, "unexpected receipt iteration")
    require(receipt["contract_id"] == collection_config["contract_id"], "receipt contract id mismatch")
    require(str(receipt["provider_name"]).strip() != "", "receipt provider name is required")
    require(str(receipt["provider_host"]).strip() != "", "receipt provider host is required")
    _parse_utc_timestamp(receipt["collected_at_utc"])
    requested_start = parse_date(receipt["requested_start_date"], "requested_start_date")
    requested_end = parse_date(receipt["requested_end_date"], "requested_end_date")
    target_end = date.fromisoformat(collection_config["target_end_date"])
    require(requested_start == date.fromisoformat(collection_config["collection_start_date"]), "receipt requested start mismatch")
    require(requested_start <= requested_end <= target_end, "receipt requested window is invalid")
    require(receipt["target_end_date"] == collection_config["target_end_date"], "receipt target end mismatch")
    require(receipt["actual_start_date"] == summary.start_date, "receipt start date mismatch")
    require(receipt["actual_end_date"] == summary.end_date, "receipt end date mismatch")
    require(receipt["row_count"] == summary.row_count, "receipt row count mismatch")
    require(receipt["validated_row_count"] == summary.row_count, "receipt validated row count mismatch")
    require(receipt["symbol_count"] == summary.symbol_count, "receipt symbol count mismatch")
    expected_symbols = list(symbols_config["required_symbols"])
    require(receipt["required_symbols"] == expected_symbols, "receipt required symbols mismatch")
    require(receipt["csv_sha256"] == manifest["data_file_sha256"], "receipt CSV hash mismatch")
    require(receipt["corporate_action_adjusted"] is True, "receipt adjusted-data attestation missing")
    require(receipt["regular_session_only"] is True, "receipt regular-session attestation missing")
    require(receipt["synthetic_prices_used"] is False, "receipt synthetic data is prohibited")
    require(receipt["source_data_modified"] is False, "receipt source mutation is prohibited")
    require(isinstance(receipt["request_count"], int) and receipt["request_count"] >= summary.symbol_count, "invalid receipt request count")
    require(isinstance(receipt["per_symbol"], dict), "receipt per_symbol must be an object")
    require(set(receipt["per_symbol"]) == set(expected_symbols), "receipt per-symbol coverage mismatch")

    per_symbol_end: list[str] = []
    per_symbol_start: list[str] = []
    total_rows = 0
    for symbol in expected_symbols:
        item = receipt["per_symbol"][symbol]
        require(isinstance(item, dict), f"invalid per-symbol receipt for {symbol}")
        require(set(item) == {"row_count", "start_date", "end_date", "provider_metadata"}, f"unexpected per-symbol fields for {symbol}")
        require(isinstance(item["row_count"], int) and item["row_count"] > 0, f"invalid per-symbol row count for {symbol}")
        parse_date(item["start_date"], f"{symbol}.start_date")
        parse_date(item["end_date"], f"{symbol}.end_date")
        require(item["start_date"] <= item["end_date"], f"invalid per-symbol range for {symbol}")
        metadata = item["provider_metadata"]
        require(isinstance(metadata, dict), f"provider metadata missing for {symbol}")
        require(str(metadata.get("symbol") or "").upper() == symbol, f"provider symbol mismatch for {symbol}")
        require(str(metadata.get("request_url") or "").strip() != "", f"provider request URL missing for {symbol}")
        require(isinstance(metadata.get("attempt_count"), int) and metadata["attempt_count"] >= 1, f"provider attempt count invalid for {symbol}")
        total_rows += item["row_count"]
        per_symbol_start.append(item["start_date"])
        per_symbol_end.append(item["end_date"])
    require(total_rows == summary.row_count, "per-symbol row counts do not equal CSV row count")
    require(min(per_symbol_start) == summary.start_date, "per-symbol start dates disagree with CSV")
    require(max(per_symbol_end) == summary.end_date, "per-symbol end dates disagree with CSV")
    require(receipt["actual_end_date_all_symbols"] == min(per_symbol_end), "all-symbol end date mismatch")
    derived_complete = all(value >= collection_config["target_end_date"] for value in per_symbol_end)
    require(receipt["target_window_complete"] is derived_complete, "target completion flag is inconsistent")

    after = {name: _fingerprint(path) for name, path in paths.items()}
    require(before == after, "snapshot files changed during validation")
    return ArtifactValidation(relative.as_posix(), manifest, receipt, summary)


def _git(repository_root: Path, *args: str, binary: bool = False) -> bytes | str:
    result = subprocess.run(
        ["git", *args],
        cwd=repository_root,
        check=False,
        capture_output=True,
        text=not binary,
    )
    require(result.returncode == 0, f"git command failed: {' '.join(args)}")
    return result.stdout


def require_git_commit(repository_root: Path, commit_sha: str) -> None:
    require(bool(SHA40_RE.fullmatch(commit_sha)), "commit must be a full 40-character SHA")
    _git(repository_root, "cat-file", "-e", f"{commit_sha}^{{commit}}")


def validate_market_artifact_at_commit(
    *,
    repository_root: Path,
    public_commit: str,
    snapshot_path: str,
    expected_data_commit: str,
    symbols_config: dict[str, Any],
    collection_config: dict[str, Any],
    today: date | None = None,
) -> ArtifactValidation:
    require_git_commit(repository_root, public_commit)
    relative = _snapshot_relative_path(snapshot_path)
    listing = str(_git(repository_root, "ls-tree", "-r", "--name-only", public_commit, "--", relative.as_posix()))
    expected_paths = sorted((relative / name).as_posix() for name in REQUIRED_SNAPSHOT_FILES)
    actual_paths = sorted(line for line in listing.splitlines() if line)
    require(actual_paths == expected_paths, "public commit does not contain the exact complete snapshot")
    with tempfile.TemporaryDirectory() as directory:
        temp_root = Path(directory)
        for relative_file in expected_paths:
            content = _git(repository_root, "show", f"{public_commit}:{relative_file}", binary=True)
            destination = temp_root / relative_file
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(content if isinstance(content, bytes) else content.encode("utf-8"))
        return validate_market_artifact(
            repository_root=temp_root,
            snapshot_path=relative.as_posix(),
            expected_data_commit=expected_data_commit,
            symbols_config=symbols_config,
            collection_config=collection_config,
            today=today,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--snapshot-path", required=True)
    parser.add_argument("--data-commit", required=True)
    parser.add_argument("--public-commit")
    parser.add_argument("--symbols-config", type=Path, default=Path("config/iteration_16_symbols.json"))
    parser.add_argument("--collection-config", type=Path, default=Path("config/iteration_16_collection.json"))
    parser.add_argument("--today")
    args = parser.parse_args()
    try:
        kwargs = {
            "repository_root": args.repository_root,
            "snapshot_path": args.snapshot_path,
            "expected_data_commit": args.data_commit,
            "symbols_config": load_object(args.symbols_config),
            "collection_config": load_object(args.collection_config),
            "today": date.fromisoformat(args.today) if args.today else None,
        }
        result = (
            validate_market_artifact_at_commit(public_commit=args.public_commit, **kwargs)
            if args.public_commit
            else validate_market_artifact(**kwargs)
        )
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise SystemExit(f"market artifact validation failed: {exc}") from exc
    print(json.dumps({"snapshot_path": result.snapshot_path, "row_count": result.summary.row_count}, sort_keys=True))


if __name__ == "__main__":
    main()
