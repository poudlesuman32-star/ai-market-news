#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

API_ROOT = "https://api.github.com"
UPLOAD_ROOT = "https://uploads.github.com"
PRIVATE_REPOSITORY = "musksuman3/ai-signal-engine"
PRIVATE_REPOSITORY_ID = 1290626648
EXPECTED_FILE_COUNT = 50
MAX_PACKAGE_BYTES = 150_000_000


class HandoffPublishError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise HandoffPublishError(message)


def api(method: str, path: str, *, token: str, payload: dict[str, Any] | None = None, allowed: tuple[int, ...] = (200, 201)) -> tuple[int, Any]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        API_ROOT + path,
        data=body,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "PPI public-to-private handoff publisher",
            **({"Content-Type": "application/json"} if body is not None else {}),
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            status = int(response.status)
            raw = response.read()
    except urllib.error.HTTPError as exc:
        status = int(exc.code)
        raw = exc.read()
    value: Any = None
    if raw:
        try:
            value = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            value = raw.decode("utf-8", errors="replace")
    if status not in allowed:
        detail = value.get("message") if isinstance(value, dict) else value
        raise HandoffPublishError(f"GitHub API {method} {path} returned {status}: {detail}")
    return status, value


def deterministic_zip(source_root: Path, archive: Path) -> str:
    paths = sorted(path for path in source_root.rglob("*") if path.is_file())
    require(len(paths) == EXPECTED_FILE_COUNT, "handoff source must contain exactly 50 files")
    archive.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in paths:
            relative = path.relative_to(source_root).as_posix()
            info = zipfile.ZipInfo(relative, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            zf.writestr(info, path.read_bytes())
    require(archive.stat().st_size <= MAX_PACKAGE_BYTES, "private handoff package exceeds size limit")
    return hashlib.sha256(archive.read_bytes()).hexdigest()


def upload_asset(*, release_id: int, archive: Path, asset_name: str, token: str) -> dict[str, Any]:
    query = urllib.parse.urlencode({"name": asset_name})
    url = f"{UPLOAD_ROOT}/repos/{PRIVATE_REPOSITORY}/releases/{release_id}/assets?{query}"
    request = urllib.request.Request(
        url,
        data=archive.read_bytes(),
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/zip",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "PPI public-to-private handoff publisher",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            value = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise HandoffPublishError(f"private release asset upload returned {exc.code}: {body}") from exc
    require(isinstance(value, dict), "unexpected asset upload response")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description="Publish the exact 50-path PPI package as a private release asset")
    parser.add_argument("--package-root", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--safe-summary", type=Path, required=True)
    args = parser.parse_args()

    token = os.environ.get("PPI_PRIVATE_HANDOFF_TOKEN", "").strip()
    require(token, "PPI_PRIVATE_HANDOFF_TOKEN is required")
    run_id = int(os.environ.get("GITHUB_RUN_ID", "0") or 0)
    attempt = int(os.environ.get("GITHUB_RUN_ATTEMPT", "0") or 0)
    head_sha = os.environ.get("GITHUB_SHA", "").lower()
    require(run_id > 0 and attempt > 0 and len(head_sha) == 40, "public workflow identity is invalid")

    _, repo = api("GET", f"/repos/{PRIVATE_REPOSITORY}", token=token)
    require(isinstance(repo, dict) and int(repo.get("id", 0)) == PRIVATE_REPOSITORY_ID, "private repository identity mismatch")
    require(repo.get("private") is True and repo.get("default_branch") == "main", "private repository boundary mismatch")

    package_sha = deterministic_zip(args.package_root, args.archive)
    tag = f"ppi-r11-public-{run_id}-{attempt}"
    asset_name = f"ppi-r11-public-package-{run_id}-{attempt}.zip"
    body = (
        "Automated private PPI evidence handoff.\n\n"
        f"public_run_id: {run_id}\n"
        f"public_run_attempt: {attempt}\n"
        f"public_head_sha: {head_sha}\n"
        f"package_sha256: {package_sha}\n"
        "public_contract_id: PPI-R11-PUBLIC-ACQUISITION-003-R1\n"
        "private_contract_id: PPI-R11-BATCH-EVIDENCE-003-R1\n"
    )

    status, existing = api("GET", f"/repos/{PRIVATE_REPOSITORY}/releases/tags/{tag}", token=token, allowed=(200, 404))
    if status == 200:
        require(isinstance(existing, dict), "unexpected existing release response")
        require(f"package_sha256: {package_sha}" in str(existing.get("body", "")), "existing release package identity differs")
        assets = existing.get("assets")
        matches = [item for item in assets if isinstance(item, dict) and item.get("name") == asset_name] if isinstance(assets, list) else []
        require(len(matches) == 1, "existing private release asset is missing or duplicated")
        release = existing
        asset = matches[0]
    else:
        _, main_ref = api("GET", f"/repos/{PRIVATE_REPOSITORY}/git/ref/heads/main", token=token)
        main_sha = str((main_ref.get("object") or {}).get("sha", "")) if isinstance(main_ref, dict) else ""
        require(len(main_sha) == 40, "private main SHA is invalid")
        _, release = api(
            "POST", f"/repos/{PRIVATE_REPOSITORY}/releases", token=token,
            payload={"tag_name": tag, "target_commitish": main_sha, "name": tag, "body": body, "draft": True, "prerelease": False},
            allowed=(201,),
        )
        require(isinstance(release, dict) and int(release.get("id", 0)) > 0, "private draft release was not created")
        asset = upload_asset(release_id=int(release["id"]), archive=args.archive, asset_name=asset_name, token=token)
        _, release = api("PATCH", f"/repos/{PRIVATE_REPOSITORY}/releases/{int(release['id'])}", token=token, payload={"draft": False}, allowed=(200,))

    safe = {
        "schema_version": "1.0.0",
        "status": "private_handoff_published",
        "public_run_id": run_id,
        "public_run_attempt": attempt,
        "public_head_sha": head_sha,
        "package_sha256": package_sha,
        "package_file_count": EXPECTED_FILE_COUNT,
        "private_release_tag": tag,
        "private_release_id": int(release.get("id", 0) or 0),
        "private_asset_id": int(asset.get("id", 0) or 0),
        "private_asset_name": asset_name,
        "provider_payload_in_public_summary": False,
        "private_repository_dispatched": False,
        "authorized_actions": [],
    }
    args.safe_summary.parent.mkdir(parents=True, exist_ok=True)
    args.safe_summary.write_text(json.dumps(safe, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(safe, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except HandoffPublishError as exc:
        raise SystemExit(str(exc)) from exc
