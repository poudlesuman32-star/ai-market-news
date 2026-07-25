#!/usr/bin/env python3
from __future__ import annotations

import base64
import json
import os
import sys
from typing import Any
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

API_ROOT = "https://api.github.com"
DEFAULT_TARGET = "spoudel2010-ux/ppi-data-acquisition"
DEFAULT_BASE = "main"
BOOTSTRAP_BRANCH = "agent/bootstrap-r11-public-acquisition"
UPSTREAM_REPOSITORY = "poudlesuman32-star/ai-market-news"
UPSTREAM_SHA = "2beef2ba5b935c76e02b74df2d02b33221784e19"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def api(
    method: str,
    path: str,
    *,
    token: str,
    payload: dict[str, Any] | None = None,
    allowed_statuses: tuple[int, ...] = (200, 201),
) -> tuple[int, Any]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = Request(
        API_ROOT + path,
        data=body,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "PPI public acquisition bootstrap",
            **({"Content-Type": "application/json"} if body is not None else {}),
        },
    )
    try:
        with urlopen(request, timeout=30) as response:
            status = response.status
            raw = response.read()
    except HTTPError as exc:
        status = exc.code
        raw = exc.read()
    parsed: Any = None
    if raw:
        try:
            parsed = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            parsed = raw.decode("utf-8", errors="replace")
    if status not in allowed_statuses:
        message = parsed.get("message") if isinstance(parsed, dict) else str(parsed)
        raise RuntimeError(f"GitHub API {method} {path} returned {status}: {message}")
    return status, parsed


def read_file_sha(repository: str, path: str, branch: str, *, token: str) -> str | None:
    encoded = quote(path, safe="/")
    status, payload = api(
        "GET",
        f"/repos/{repository}/contents/{encoded}?ref={quote(branch, safe='')}",
        token=token,
        allowed_statuses=(200, 404),
    )
    if status == 404:
        return None
    require(isinstance(payload, dict), f"Unexpected content response for {path}")
    sha = payload.get("sha")
    require(isinstance(sha, str) and sha, f"Missing blob SHA for {path}")
    return sha


def put_file(
    repository: str,
    path: str,
    content: str,
    *,
    branch: str,
    message: str,
    token: str,
) -> None:
    current_sha = read_file_sha(repository, path, branch, token=token)
    payload: dict[str, Any] = {
        "message": message,
        "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
        "branch": branch,
    }
    if current_sha:
        payload["sha"] = current_sha
    encoded = quote(path, safe="/")
    api("PUT", f"/repos/{repository}/contents/{encoded}", token=token, payload=payload)


def get_ref_sha(repository: str, branch: str, *, token: str) -> str | None:
    status, payload = api(
        "GET",
        f"/repos/{repository}/git/ref/heads/{quote(branch, safe='')}",
        token=token,
        allowed_statuses=(200, 404, 409),
    )
    if status in {404, 409}:
        return None
    require(isinstance(payload, dict), "Unexpected ref response")
    obj = payload.get("object")
    require(isinstance(obj, dict), "Missing ref object")
    sha = obj.get("sha")
    require(isinstance(sha, str) and len(sha) == 40, "Missing main commit SHA")
    return sha


def ensure_repository_initialized(repository: str, *, token: str) -> str:
    main_sha = get_ref_sha(repository, DEFAULT_BASE, token=token)
    if main_sha:
        return main_sha
    placeholder = (
        "# PPI Data Acquisition\n\n"
        "This public repository is being initialized through a reviewed, manual-only cross-repository workflow.\n"
    )
    payload = {
        "message": "Initialize public acquisition repository",
        "content": base64.b64encode(placeholder.encode("utf-8")).decode("ascii"),
        "branch": DEFAULT_BASE,
    }
    api(
        "PUT",
        f"/repos/{repository}/contents/README.md",
        token=token,
        payload=payload,
        allowed_statuses=(201,),
    )
    main_sha = get_ref_sha(repository, DEFAULT_BASE, token=token)
    require(main_sha is not None, "Target repository initialization did not create main")
    return main_sha


def ensure_branch(repository: str, branch: str, base_sha: str, *, token: str) -> None:
    existing = get_ref_sha(repository, branch, token=token)
    if existing:
        return
    api(
        "POST",
        f"/repos/{repository}/git/refs",
        token=token,
        payload={"ref": f"refs/heads/{branch}", "sha": base_sha},
        allowed_statuses=(201,),
    )


def target_files() -> dict[str, str]:
    cumulative = ["AAPL", "MU", "NVDA", "AMD", "AVGO", "INTC", "TSM", "ARM", "QCOM", "MRVL", "GFS", "TXN"]
    contract = {
        "schema_version": "1.0.0",
        "contract_id": "PPI-R11-PUBLIC-ACQUISITION-003",
        "status": "proposed",
        "purpose": "Public provider retrieval and immutable acquisition evidence only",
        "batch_sequence": 3,
        "new_tickers": ["QCOM", "MRVL", "GFS", "TXN"],
        "cumulative_tickers": cumulative,
        "required_evidence_categories_per_ticker": 4,
        "expected_bundle_count": 48,
        "maximum_evidence_age_hours": 168,
        "upstream_public_code": {"repository": UPSTREAM_REPOSITORY, "commit_sha": UPSTREAM_SHA},
        "private_curation_authorized": False,
        "private_calculation_authorized": False,
        "scoring_authorized": False,
        "ticker_approval_authorized": False,
        "registry_mutation_authorized": False,
        "production_authorized": False,
        "r12_authorized": False,
        "broker_or_trading_authorized": False,
        "authorized_actions": [],
    }
    batch = {
        "schema_version": "1.0.0",
        "batch_sequence": 3,
        "new_tickers": ["QCOM", "MRVL", "GFS", "TXN"],
        "cumulative_tickers": cumulative,
        "expected_bundle_count": 48,
        "collection_mode": "manual_only",
        "private_dispatch_enabled": False,
    }
    readme = """# PPI Data Acquisition

Public, manual-only provider retrieval for the PPI program.

## Boundary

This repository may retrieve provider data, perform objective schema/timestamp checks, sanitize retained output, hash payloads, and publish immutable GitHub Actions artifacts. It must not perform private curation, proprietary calculations, scoring, ticker approval, countability decisions, registry mutation, production activation, broker access, orders, or trading.

## Repository roles

- `spoudel2010-ux/ppi-data-acquisition`: public retrieval and acquisition receipts.
- `poudlesuman32-star/ai-market-news`: reusable public collection code and source definitions.
- `musksuman3/ai-signal-engine`: private curation, calculation, scoring, countability, and registry proposals.
- `jansuman200001-prog/MMM`: sanitized audit and roadmap status.

## Execution policy

Collection workflows begin as `workflow_dispatch` only. There are no schedules and no automatic private-repository dispatches. A private run must be started explicitly with an exact public run ID, attempt, head SHA, artifact ID, and digest.

The batch-3 contract is proposed until the provider-specific collector implementation and licensing review are completed.
"""
    boundary_workflow = """name: Validate PPI public acquisition boundary

on:
  workflow_dispatch:

permissions:
  contents: read

jobs:
  validate:
    runs-on: ubuntu-latest
    timeout-minutes: 5
    steps:
      - uses: actions/checkout@v4
        with:
          persist-credentials: false
      - name: Validate contract and manual-only boundary
        run: |
          set -euo pipefail
          python - <<'PY'
          import json
          from pathlib import Path

          contract = json.loads(Path('contracts/PPI-R11-PUBLIC-ACQUISITION-003.json').read_text(encoding='utf-8'))
          batch = json.loads(Path('config/r11_batch_003.json').read_text(encoding='utf-8'))
          workflow = Path('.github/workflows/validate-public-acquisition-boundary.yml').read_text(encoding='utf-8')

          assert contract['contract_id'] == 'PPI-R11-PUBLIC-ACQUISITION-003'
          assert contract['status'] == 'proposed'
          assert contract['batch_sequence'] == 3
          assert contract['new_tickers'] == ['QCOM', 'MRVL', 'GFS', 'TXN']
          assert len(contract['cumulative_tickers']) == 12
          assert contract['expected_bundle_count'] == 48
          assert contract['maximum_evidence_age_hours'] == 168
          assert batch['collection_mode'] == 'manual_only'
          assert batch['private_dispatch_enabled'] is False
          assert 'workflow_dispatch:' in workflow
          assert 'schedule:' not in workflow
          for key in (
              'private_curation_authorized', 'private_calculation_authorized',
              'scoring_authorized', 'ticker_approval_authorized',
              'registry_mutation_authorized', 'production_authorized',
              'r12_authorized', 'broker_or_trading_authorized',
          ):
              assert contract[key] is False, key
          assert contract['authorized_actions'] == []
          PY
"""
    return {
        "README.md": readme,
        "contracts/PPI-R11-PUBLIC-ACQUISITION-003.json": json.dumps(contract, indent=2, sort_keys=True) + "\n",
        "config/r11_batch_003.json": json.dumps(batch, indent=2, sort_keys=True) + "\n",
        ".github/workflows/validate-public-acquisition-boundary.yml": boundary_workflow,
    }


def ensure_draft_pr(repository: str, *, token: str) -> str:
    owner = repository.split("/", 1)[0]
    _, existing = api(
        "GET",
        f"/repos/{repository}/pulls?state=open&head={quote(owner + ':' + BOOTSTRAP_BRANCH, safe=':')}&base={DEFAULT_BASE}",
        token=token,
    )
    if isinstance(existing, list) and existing:
        url = existing[0].get("html_url")
        require(isinstance(url, str), "Existing PR is missing a URL")
        return url
    _, created = api(
        "POST",
        f"/repos/{repository}/pulls",
        token=token,
        payload={
            "title": "Bootstrap manual-only PPI public acquisition boundary",
            "head": BOOTSTRAP_BRANCH,
            "base": DEFAULT_BASE,
            "draft": True,
            "body": (
                "## Summary\n"
                "- initialize the public PPI acquisition boundary\n"
                "- add the proposed batch-3 acquisition contract and exact twelve-ticker scope\n"
                "- add a manual-only boundary validation workflow\n"
                "- keep schedules, private dispatch, scoring, registry writes, production, and trading disabled\n\n"
                "## Follow-up\n"
                "Provider-specific retrieval code will be added in a separately reviewed PR after licensing and output-schema review."
            ),
        },
        allowed_statuses=(201,),
    )
    require(isinstance(created, dict), "Unexpected PR creation response")
    url = created.get("html_url")
    require(isinstance(url, str), "Created PR is missing a URL")
    return url


def main() -> int:
    token = os.environ.get("PPI_CROSS_REPOSITORY_AUTOMATION", "").strip()
    repository = os.environ.get("TARGET_REPOSITORY", DEFAULT_TARGET).strip()
    require(bool(token), "PPI_CROSS_REPOSITORY_AUTOMATION is not configured")
    require(repository == DEFAULT_TARGET, f"Unexpected target repository: {repository}")

    _, metadata = api("GET", f"/repos/{repository}", token=token)
    require(isinstance(metadata, dict), "Unexpected repository metadata")
    require(metadata.get("visibility") == "public", "Target repository must remain public")
    require(metadata.get("archived") is False, "Target repository is archived")

    base_sha = ensure_repository_initialized(repository, token=token)
    ensure_branch(repository, BOOTSTRAP_BRANCH, base_sha, token=token)
    for path, content in target_files().items():
        put_file(
            repository,
            path,
            content,
            branch=BOOTSTRAP_BRANCH,
            message=f"Bootstrap public acquisition: {path}",
            token=token,
        )
    pr_url = ensure_draft_pr(repository, token=token)
    print(json.dumps({"status": "bootstrap_pr_ready", "repository": repository, "pull_request": pr_url}, sort_keys=True))
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as summary:
            summary.write("## PPI public acquisition bootstrap\n\n")
            summary.write(f"Draft PR: {pr_url}\n")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # fail closed without exposing the token
        print(f"bootstrap failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
