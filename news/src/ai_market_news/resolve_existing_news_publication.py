from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

from .collector_common import CollectorError, require
from .verify_news_publication_transaction import verify_transaction


def git(repository_root: Path, *args: str) -> str:
    try:
        completed = subprocess.run(
            ["git", "-C", str(repository_root), *args],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        raise CollectorError(f"git command failed: {' '.join(args)}") from exc
    return completed.stdout.strip()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CollectorError(f"cannot read valid JSON: {path}") from exc
    require(isinstance(value, dict), f"expected JSON object: {path}")
    return value


def resolve_existing_publication(
    *, repository_root: Path, news_path: Path, receipt_path: Path
) -> dict[str, Any]:
    candidate_digest = sha256_file(news_path)
    receipt_digest = sha256_file(receipt_path)
    digest_matches: list[tuple[Path, dict[str, Any]]] = []

    for manifest_path in sorted(repository_root.glob("snapshots/*/news_manifest.json")):
        manifest = read_json(manifest_path)
        published_digest = manifest.get("news_file_sha256", manifest.get("file_sha256"))
        if published_digest == candidate_digest:
            digest_matches.append((manifest_path, manifest))

    if not digest_matches:
        return {
            "schema_version": "1.0.0",
            "status": "not_found",
            "candidate_sha256": candidate_digest,
        }

    require(len(digest_matches) == 1, "candidate digest appears in multiple published manifests")
    manifest_path, manifest = digest_matches[0]
    require(manifest.get("receipt_file_sha256") == receipt_digest, "published receipt digest mismatch")

    snapshot_path = str(manifest.get("snapshot_path", ""))
    require(snapshot_path.startswith("snapshots/") and ".." not in snapshot_path, "invalid published snapshot path")
    manifest_relative = str(manifest_path.relative_to(repository_root))
    public_commits = [
        line
        for line in git(repository_root, "log", "--format=%H", "--diff-filter=A", "--", manifest_relative).splitlines()
        if line
    ]
    require(len(public_commits) == 1, "cannot resolve unique Commit B for published manifest")
    public_commit = public_commits[0]
    data_commit = str(manifest.get("data_commit", ""))
    previous_head = git(repository_root, "rev-parse", f"{data_commit}^")

    descendants = [
        line
        for line in git(repository_root, "rev-list", "--first-parent", "--reverse", f"{public_commit}..HEAD").splitlines()
        if line
    ]
    require(bool(descendants), "cannot resolve Commit C for published manifest")
    pointer_commit = descendants[0]

    verification = verify_transaction(
        repository_root=repository_root,
        previous_head=previous_head,
        data_commit=data_commit,
        public_commit=public_commit,
        pointer_commit=pointer_commit,
        snapshot_path=snapshot_path,
    )
    require(verification.get("valid") is True, "existing publication transaction is invalid")

    published_news_path = repository_root / snapshot_path / "news.jsonl"
    published_receipt_path = repository_root / snapshot_path / "collection_receipt.json"
    require(sha256_file(published_news_path) == candidate_digest, "published news bytes mismatch")
    require(sha256_file(published_receipt_path) == receipt_digest, "published receipt bytes mismatch")

    return {
        "schema_version": "1.0.0",
        "status": "found",
        "candidate_sha256": candidate_digest,
        "receipt_sha256": receipt_digest,
        "previous_head": previous_head,
        "data_commit": data_commit,
        "public_commit": public_commit,
        "pointer_commit": pointer_commit,
        "snapshot_path": snapshot_path,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Resolve an exact previously published public-news transaction")
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--news", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    result = resolve_existing_publication(
        repository_root=args.repository_root,
        news_path=args.news,
        receipt_path=args.receipt,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
