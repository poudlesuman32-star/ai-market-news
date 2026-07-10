from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from .collector_common import CollectorError, require

SHA_RE = re.compile(r"^[a-f0-9]{40}$", re.IGNORECASE)


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CollectorError(f"{path}: invalid JSON: {exc}") from exc
    require(isinstance(value, dict), f"{path}: expected a JSON object")
    return value


def build_latest_pointer(*, manifest: dict[str, Any], public_commit: str) -> dict[str, Any]:
    require(manifest.get("schema_version") == "1.0.0", "unsupported news manifest schema")
    require(manifest.get("source_repository") == "poudlesuman32-star/ai-market-news", "unexpected source repository")
    require(manifest.get("collection_complete") is True, "manifest collection is incomplete")
    require(manifest.get("synthetic_content_used") is False, "manifest reports synthetic content")
    require(manifest.get("source_content_modified") is False, "manifest reports modified source content")
    require(manifest.get("private_content_excluded") is True, "manifest does not confirm private-content exclusion")
    snapshot_path = str(manifest.get("snapshot_path", ""))
    require(snapshot_path.startswith("snapshots/") and ".." not in snapshot_path, "invalid snapshot_path")
    data_commit = str(manifest.get("data_commit", ""))
    require(SHA_RE.fullmatch(data_commit) is not None, "invalid data_commit")
    require(SHA_RE.fullmatch(public_commit) is not None, "public_commit must be a 40-character SHA")
    require(public_commit != data_commit, "public_commit must differ from data_commit")
    return {
        "schema_version": "1.0.0",
        "snapshot_path": snapshot_path,
        "data_commit": data_commit,
        "public_commit": public_commit,
        "collection_complete": True,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the public-news latest pointer")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--public-commit", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    pointer = build_latest_pointer(manifest=load_json(args.manifest), public_commit=args.public_commit)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(pointer, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
