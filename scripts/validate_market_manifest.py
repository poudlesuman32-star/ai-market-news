"""Validate a public market manifest and its pinned CSV."""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from scripts.contract_common import (
    SHA40_RE,
    SHA256_RE,
    CsvSummary,
    load_object,
    market_artifact_id,
    require,
    safe_relative_path,
    sha256,
)
from scripts.validate_market_csv import validate_market_csv


def validate_market_manifest(
    manifest_path: Path,
    *,
    market_root: Path,
    symbols_config: dict[str, Any],
    collection_config: dict[str, Any],
    today: date | None = None,
) -> CsvSummary:
    manifest = load_object(manifest_path)
    required_keys = {
        "manifest_version", "contract_id", "artifact_id", "provider_name",
        "source_repository", "source_commit_sha", "data_file_path",
        "data_file_sha256", "data_format", "encoding", "calendar", "timezone",
        "corporate_action_adjusted", "regular_session_only", "symbol_count",
        "row_count", "symbols", "start_date", "end_date", "source_data_modified",
        "synthetic_prices_used",
    }
    allowed_keys = required_keys | {"notes"}
    require(set(manifest) in (required_keys, allowed_keys), "manifest fields do not match the contract")
    require(manifest["manifest_version"] == "1.0.0", "unexpected manifest version")
    require(manifest["contract_id"] == collection_config["contract_id"], "unexpected contract id")
    require(str(manifest["provider_name"]).strip() != "", "provider name is required")
    require(manifest["source_repository"] == collection_config["source_repository"], "unexpected source repository")
    require(bool(SHA40_RE.fullmatch(str(manifest["source_commit_sha"]))), "invalid source commit SHA")
    require(manifest["data_format"] == "csv", "unexpected data format")
    require(manifest["encoding"] == "utf-8", "unexpected encoding")
    require(manifest["calendar"] == collection_config["calendar"], "unexpected calendar")
    require(manifest["timezone"] == collection_config["timezone"], "unexpected timezone")
    require(manifest["corporate_action_adjusted"] is True, "corporate-action adjustment is required")
    require(manifest["regular_session_only"] is True, "regular-session-only data is required")
    require(manifest["source_data_modified"] is False, "modified source data is prohibited")
    require(manifest["synthetic_prices_used"] is False, "synthetic prices are prohibited")

    relative_path = safe_relative_path(manifest["data_file_path"], expected_prefix="snapshots")
    data_path = (market_root / relative_path).resolve()
    root = market_root.resolve()
    require(data_path.is_relative_to(root), "market data path escapes the market root")
    require(data_path.is_file(), "market CSV does not exist")
    actual_hash = sha256(data_path)
    require(bool(SHA256_RE.fullmatch(str(manifest["data_file_sha256"]))), "invalid data SHA-256")
    require(manifest["data_file_sha256"] == actual_hash, "market CSV hash mismatch")

    summary = validate_market_csv(
        data_path,
        symbols_config=symbols_config,
        collection_config=collection_config,
        today=today,
    )
    require(manifest["row_count"] == summary.row_count, "manifest row count mismatch")
    require(manifest["symbol_count"] == summary.symbol_count, "manifest symbol count mismatch")
    require(tuple(manifest["symbols"]) == summary.symbols, "manifest symbols mismatch")
    require(manifest["start_date"] == summary.start_date, "manifest start date mismatch")
    require(manifest["end_date"] == summary.end_date, "manifest end date mismatch")

    expected_id = market_artifact_id(
        source_repository=manifest["source_repository"],
        source_commit_sha=manifest["source_commit_sha"],
        data_file_path=manifest["data_file_path"],
        data_file_sha256=manifest["data_file_sha256"],
    )
    require(manifest["artifact_id"] == expected_id, "artifact identity mismatch")
    return summary
