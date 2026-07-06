"""Shared helpers for the frozen Iteration 16 public market contract."""
from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

SHA40_RE = re.compile(r"^[0-9a-f]{40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class ContractError(ValueError):
    """Raised when a public artifact violates the frozen contract."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractError(message)


def load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"{path} must contain a JSON object")
    return value


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def market_artifact_id(
    *, source_repository: str, source_commit_sha: str, data_file_path: str, data_file_sha256: str
) -> str:
    payload = "\x1f".join(
        [source_repository, source_commit_sha, data_file_path, data_file_sha256]
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def parse_date(value: Any, field: str, line_number: int | None = None) -> date:
    location = f" at line {line_number}" if line_number is not None else ""
    try:
        return date.fromisoformat(str(value).strip())
    except ValueError as exc:
        raise ContractError(f"invalid {field}{location}") from exc


def parse_positive(value: Any, field: str, line_number: int) -> float:
    try:
        number = float(str(value).strip())
    except ValueError as exc:
        raise ContractError(f"invalid {field} at line {line_number}") from exc
    require(math.isfinite(number) and number > 0.0, f"invalid {field} at line {line_number}")
    return number


def safe_relative_path(value: Any, *, expected_prefix: str | None = None) -> Path:
    text = str(value).strip()
    require(text != "", "path must not be empty")
    path = Path(text)
    require(not path.is_absolute(), "absolute paths are prohibited")
    require(".." not in path.parts, "parent path components are prohibited")
    if expected_prefix is not None:
        require(path.parts and path.parts[0] == expected_prefix, f"path must begin with {expected_prefix}/")
    return path


@dataclass(frozen=True)
class CsvSummary:
    row_count: int
    symbol_count: int
    symbols: tuple[str, ...]
    start_date: str
    end_date: str
