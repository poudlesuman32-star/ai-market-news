from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Any

from .build_news_latest_pointer import load_json
from .collector_common import CollectorError, require

SHA_RE = re.compile(r"^[a-f0-9]{40}$", re.IGNORECASE)


def git(repository_root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repository_root), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def changed_paths(repository_root: Path, parent: str, child: str) -> list[str]:
    output = git(repository_root, "diff", "--name-only", parent, child)
    return sorted(line for line in output.splitlines() if line)


def commit_parent(repository_root: Path, commit: str) -> str:
    return git(repository_root, "rev-parse", f"{commit}^")


def read_json_at(repository_root: Path, commit: str, path: str) -> dict[str, Any]:
    try:
        payload = git(repository_root, "show", f"{commit}:{path}")
        value = json.loads(payload)
    except (subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        raise CollectorError(f"cannot read valid JSON at {commit}:{path}") from exc
    require(isinstance(value, dict), f"{commit}:{path} must contain an object")
    return value


def verify_transaction(
    *,
    repository_root: Path,
    previous_head: str,
    data_commit: str,
    public_commit: str,
    pointer_commit: str,
    snapshot_path: str,
) -> dict[str, Any]:
    for name, value in (
        ("previous_head", previous_head),
        ("data_commit", data_commit),
        ("public_commit", public_commit),
        ("pointer_commit", pointer_commit),
    ):
        require(SHA_RE.fullmatch(value) is not None, f"{name} must be a 40-character SHA")
    require(snapshot_path.startswith("snapshots/") and ".." not in snapshot_path, "invalid snapshot_path")
    require(commit_parent(repository_root, data_commit) == previous_head, "Commit A parent is not the previous branch head")
    require(commit_parent(repository_root, public_commit) == data_commit, "Commit B parent is not Commit A")
    require(commit_parent(repository_root, pointer_commit) == public_commit, "Commit C parent is not Commit B")

    data_paths = [f"{snapshot_path}/collection_receipt.json", f"{snapshot_path}/news.jsonl"]
    manifest_path = f"{snapshot_path}/news_manifest.json"
    require(changed_paths(repository_root, previous_head, data_commit) == sorted(data_paths), "Commit A changed unexpected paths")
    require(changed_paths(repository_root, data_commit, public_commit) == [manifest_path], "Commit B changed unexpected paths")
    require(changed_paths(repository_root, public_commit, pointer_commit) == ["latest.json"], "Commit C changed unexpected paths")

    manifest = read_json_at(repository_root, public_commit, manifest_path)
    require(manifest.get("data_commit") == data_commit, "manifest data_commit mismatch")
    require(manifest.get("snapshot_path") == snapshot_path, "manifest snapshot_path mismatch")
    require(manifest.get("collection_complete") is True, "manifest is incomplete")
    require(manifest.get("synthetic_content_used") is False, "manifest reports synthetic content")
    require(manifest.get("source_content_modified") is False, "manifest reports modified content")
    require(manifest.get("private_content_excluded") is True, "manifest does not confirm private-content exclusion")

    pointer = read_json_at(repository_root, pointer_commit, "latest.json")
    expected_pointer = {
        "schema_version": "1.0.0",
        "snapshot_path": snapshot_path,
        "data_commit": data_commit,
        "public_commit": public_commit,
        "collection_complete": True,
    }
    require(pointer == expected_pointer, "latest.json does not match the verified transaction")

    try:
        git(repository_root, "cat-file", "-e", f"{previous_head}:{snapshot_path}")
    except subprocess.CalledProcessError:
        pass
    else:
        raise CollectorError("snapshot path already existed at the previous branch head")

    return {
        "valid": True,
        "previous_head": previous_head,
        "data_commit": data_commit,
        "public_commit": public_commit,
        "pointer_commit": pointer_commit,
        "snapshot_path": snapshot_path,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify the immutable public-news transaction")
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--previous-head", required=True)
    parser.add_argument("--data-commit", required=True)
    parser.add_argument("--public-commit", required=True)
    parser.add_argument("--pointer-commit", required=True)
    parser.add_argument("--snapshot-path", required=True)
    args = parser.parse_args(argv)
    report = verify_transaction(
        repository_root=args.repository_root,
        previous_head=args.previous_head,
        data_commit=args.data_commit,
        public_commit=args.public_commit,
        pointer_commit=args.pointer_commit,
        snapshot_path=args.snapshot_path,
    )
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
