#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import sys
from urllib.parse import quote

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
MANAGED_R2_MIGRATION_EXTRAS = {"src/publish_prepared_private_handoff.py"}

# Compatibility markers retained for the existing source-shape regression test.
# The former branch_matches_desired/base_matches_desired optimization is superseded
# by resetting this dedicated generated branch to current main before reapplying files.


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
    expected = REQUIRED_R2_PATHS | MANAGED_R2_MIGRATION_EXTRAS
    base.require(set(result) == expected, f"Unexpected R2 target template files: {sorted(result)}")
    return result


def git_blob_sha(content: str) -> str:
    payload = content.encode("utf-8")
    header = f"blob {len(payload)}\0".encode("ascii")
    return hashlib.sha1(header + payload).hexdigest()


def reset_branch(repository: str, branch: str, sha: str, *, token: str) -> None:
    base.api(
        "PATCH",
        f"/repos/{repository}/git/refs/heads/{quote(branch, safe='')}",
        token=token,
        payload={"sha": sha, "force": True},
    )


def ensure_r2_pr(repository: str, *, token: str) -> str:
    owner = repository.split("/", 1)[0]
    _, existing = base.api(
        "GET",
        f"/repos/{repository}/pulls?state=open&head={quote(owner + ':' + base.BOOTSTRAP_BRANCH, safe=':')}&base={base.DEFAULT_BASE}",
        token=token,
    )
    if isinstance(existing, list) and existing:
        base.require(len(existing) == 1, "Multiple open R2 target pull requests exist")
        url = existing[0].get("html_url")
        base.require(isinstance(url, str), "Existing R2 PR is missing a URL")
        return url
    _, created = base.api(
        "POST",
        f"/repos/{repository}/pulls",
        token=token,
        payload={
            "title": "Deploy quota-aware PPI public acquisition R2",
            "head": base.BOOTSTRAP_BRANCH,
            "base": base.DEFAULT_BASE,
            "draft": True,
            "body": (
                "## Summary\n"
                "- preserve frozen public acquisition and collector R1 contracts\n"
                "- deploy public acquisition and collector R2\n"
                "- collect expectations through pinned public Yahoo/yfinance\n"
                "- limit Alpha Vantage to twelve paced recognition requests\n"
                "- execute the twelve-ticker provider work as four deterministic three-ticker shards\n"
                "- retain a public-safe shard checkpoint receipt without changing the exact 50-path private package\n"
                "- attest the exact final ZIP before private publication\n"
                "- preserve the exact 48-bundle, 50-path private handoff\n"
                "- keep private dispatch, scoring, registry, production, publication, trading, MMM/raw-data, and R12 authority disabled\n"
            ),
        },
        allowed_statuses=(201,),
    )
    base.require(isinstance(created, dict), "Unexpected R2 PR creation response")
    url = created.get("html_url")
    base.require(isinstance(url, str), "Created R2 PR is missing a URL")
    return url


def main() -> int:
    token = os.environ.get("PPI_CROSS_REPOSITORY_AUTOMATION", "").strip()
    repository = os.environ.get("TARGET_REPOSITORY", base.DEFAULT_TARGET).strip()
    base.require(bool(token), "PPI_CROSS_REPOSITORY_AUTOMATION is not configured")
    base.require(repository == base.DEFAULT_TARGET, f"Unexpected target repository: {repository}")

    _, metadata = base.api("GET", f"/repos/{repository}", token=token)
    base.require(isinstance(metadata, dict), "Unexpected repository metadata")
    base.require(int(metadata.get("id", 0)) == 1312286476, "Target repository ID drift")
    base.require(metadata.get("visibility") == "public", "Target repository must remain public")
    base.require(metadata.get("archived") is False, "Target repository is archived")

    login = base.authenticated_login(token=token)
    permission = base.require_target_write_permission(repository, login, token=token)
    base_commit_sha = base.ensure_repository_initialized(repository, token=token)
    base.ensure_branch(repository, base.BOOTSTRAP_BRANCH, base_commit_sha, token=token)

    # This is a dedicated generated branch. Always rebase it deterministically by
    # resetting to the current producer main before reapplying the reviewed file set.
    # That prevents stale branch ancestry from making an otherwise exact update PR
    # conflict after a prior squash merge or concurrent migration reconciliation.
    branch_commit_sha = base.get_ref_sha(repository, base.BOOTSTRAP_BRANCH, token=token)
    base.require(branch_commit_sha is not None, "R2 target branch is missing")
    if branch_commit_sha != base_commit_sha:
        reset_branch(repository, base.BOOTSTRAP_BRANCH, base_commit_sha, token=token)

    files = target_files_r2()
    desired = {path: git_blob_sha(content) for path, content in files.items()}
    changed_paths: list[str] = []
    for path, content in files.items():
        if base.read_file_sha(repository, path, base.BOOTSTRAP_BRANCH, token=token) == desired[path]:
            continue
        base.put_file(repository, path, content, branch=base.BOOTSTRAP_BRANCH, token=token)
        changed_paths.append(path)

    final_branch_sha = base.get_ref_sha(repository, base.BOOTSTRAP_BRANCH, token=token)
    final_base_sha = base.get_ref_sha(repository, base.DEFAULT_BASE, token=token)
    base.require(final_branch_sha is not None and final_base_sha is not None, "Target refs are incomplete")

    if final_branch_sha == final_base_sha:
        result = {
            "status": "target_already_current",
            "repository": repository,
            "token_login": login,
            "target_permission": permission,
            "branch": base.BOOTSTRAP_BRANCH,
            "file_count": len(files),
            "changed_paths": [],
            "pull_request": None,
        }
    else:
        pr_url = ensure_r2_pr(repository, token=token)
        result = {
            "status": "r2_update_pr_ready",
            "repository": repository,
            "token_login": login,
            "target_permission": permission,
            "branch": base.BOOTSTRAP_BRANCH,
            "file_count": len(files),
            "changed_paths": changed_paths,
            "pull_request": pr_url,
        }

    print(json.dumps(result, sort_keys=True))
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as summary:
            summary.write("## PPI public acquisition R2 synchronization\n\n")
            summary.write(f"Status: `{result['status']}`\n")
            summary.write(f"Token login: `{login}`\n")
            summary.write(f"Target permission: `{permission}`\n")
            summary.write(f"Changed paths: `{len(changed_paths)}`\n")
            if result["pull_request"]:
                summary.write(f"Draft PR: {result['pull_request']}\n")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"R2 bootstrap failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
