#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

import bootstrap_ppi_data_acquisition as base

REQUIRED_R2_PATHS = {
    "README.md",
    ".gitignore",
    ".github/workflows/collect-r11-public-evidence.yml",
    "config/r11_batch_003.json",
    "config/provider_licensing_dispositions.json",
    "contracts/PPI-R11-PUBLIC-ACQUISITION-003.json",
    "contracts/PPI-R11-PUBLIC-ACQUISITION-003-R1.json",
    "contracts/PPI-R11-PUBLIC-ACQUISITION-003-R2.json",
    "contracts/PPI-PUBLIC-COLLECTOR-003-R1.json",
    "contracts/PPI-PUBLIC-COLLECTOR-003-R2.json",
    "src/collect_raw_provider_evidence.py",
    "src/collect_raw_provider_evidence_r2.py",
    "src/fetch_yfinance_expectations.py",
    "src/publish_private_handoff.py",
    "tests/test_public_boundary.py",
}


def target_files_r2() -> dict[str, str]:
    base.require(base.TEMPLATE_ROOT.is_dir(), f"Missing template root: {base.TEMPLATE_ROOT}")
    result: dict[str, str] = {}
    for path in sorted(base.TEMPLATE_ROOT.rglob("*")):
        if not path.is_file():
            continue
        base.require(not path.is_symlink(), f"Template symlink is forbidden: {path}")
        relative = path.relative_to(base.TEMPLATE_ROOT).as_posix()
        base.require(relative and not relative.startswith("../"), f"Unsafe template path: {relative}")
        result[relative] = path.read_text(encoding="utf-8")
    base.require(set(result) == REQUIRED_R2_PATHS, f"Unexpected R2 target template files: {sorted(result)}")
    return result


def main() -> int:
    base.target_files = target_files_r2
    return base.main()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"R2 bootstrap failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
