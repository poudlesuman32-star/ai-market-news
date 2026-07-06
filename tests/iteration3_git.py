from __future__ import annotations

import subprocess
from pathlib import Path

from scripts.build_latest_pointer import build_latest_pointer, write_latest_pointer
from scripts.build_market_manifest import build_market_manifest, write_manifest
from tests.iteration3_fixture import COLLECTION_CONFIG, SNAPSHOT_PATH, SYMBOLS_CONFIG, TODAY, write_data_files


def run_git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True).stdout.strip()


def init_repo(root: Path) -> str:
    run_git(root, "init", "-b", "main")
    run_git(root, "config", "user.name", "Iteration Test")
    run_git(root, "config", "user.email", "iteration-test@localhost")
    (root / "README.md").write_text("fixture repository\n", encoding="utf-8")
    run_git(root, "add", "README.md")
    run_git(root, "commit", "-m", "foundation")
    return run_git(root, "rev-parse", "HEAD")


def create_three_commit_repo(root: Path) -> dict[str, str]:
    foundation = init_repo(root)
    snapshot = write_data_files(root)
    run_git(root, "add", SNAPSHOT_PATH)
    run_git(root, "commit", "-m", "data snapshot")
    data_commit = run_git(root, "rev-parse", "HEAD")
    manifest = build_market_manifest(
        data_file=snapshot / "market_prices.csv",
        data_file_path=f"{SNAPSHOT_PATH}/market_prices.csv",
        provider_name="Fixture Provider",
        source_repository=COLLECTION_CONFIG["source_repository"],
        source_commit_sha=data_commit,
        symbols_config=SYMBOLS_CONFIG,
        collection_config=COLLECTION_CONFIG,
        notes="three-commit fixture",
        today=TODAY,
    )
    write_manifest(snapshot / "market_artifact_manifest.json", manifest)
    run_git(root, "add", f"{SNAPSHOT_PATH}/market_artifact_manifest.json")
    run_git(root, "commit", "-m", "snapshot manifest")
    public_commit = run_git(root, "rev-parse", "HEAD")
    pointer = build_latest_pointer(
        repository_root=root,
        snapshot_path=SNAPSHOT_PATH,
        data_commit=data_commit,
        public_commit=public_commit,
        target_end_date="2026-07-24",
        symbols_config=SYMBOLS_CONFIG,
        collection_config=COLLECTION_CONFIG,
        today=TODAY,
    )
    write_latest_pointer(root / "latest.json", pointer)
    run_git(root, "add", "latest.json")
    run_git(root, "commit", "-m", "latest pointer")
    return {
        "foundation": foundation,
        "data_commit": data_commit,
        "public_commit": public_commit,
        "pointer_commit": run_git(root, "rev-parse", "HEAD"),
    }
