"""Validate the public latest.json pointer."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from scripts.contract_common import SHA40_RE, load_object, require, safe_relative_path


def validate_latest_pointer(pointer_path: Path, *, collection_config: dict[str, Any]) -> dict[str, Any]:
    pointer = load_object(pointer_path)
    expected_fields = {
        "schema_version", "snapshot_path", "data_commit", "public_commit",
        "target_end_date", "target_window_complete",
    }
    require(set(pointer) == expected_fields, "latest pointer fields do not match the contract")
    require(pointer["schema_version"] == "1.0.0", "unexpected latest pointer version")
    safe_relative_path(pointer["snapshot_path"], expected_prefix="snapshots")
    require(bool(SHA40_RE.fullmatch(str(pointer["data_commit"]))), "invalid data commit SHA")
    require(bool(SHA40_RE.fullmatch(str(pointer["public_commit"]))), "invalid public commit SHA")
    require(pointer["target_end_date"] == collection_config["target_end_date"], "unexpected target end date")
    require(isinstance(pointer["target_window_complete"], bool), "target_window_complete must be boolean")
    return pointer
