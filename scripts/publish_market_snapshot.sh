#!/usr/bin/env bash
set -euo pipefail

: "${GITHUB_REF:?GITHUB_REF is required}"
: "${GITHUB_REPOSITORY:?GITHUB_REPOSITORY is required}"
: "${GITHUB_RUN_ID:?GITHUB_RUN_ID is required}"
: "${GITHUB_RUN_ATTEMPT:?GITHUB_RUN_ATTEMPT is required}"
: "${GITHUB_SHA:?GITHUB_SHA is required}"
: "${GITHUB_ENV:?GITHUB_ENV is required}"
: "${GITHUB_STEP_SUMMARY:?GITHUB_STEP_SUMMARY is required}"
: "${RUNNER_TEMP:?RUNNER_TEMP is required}"

DATA_BRANCH="${DATA_BRANCH:-iteration-16-market-data}"
export DATA_BRANCH

if [[ "$GITHUB_REF" != "refs/heads/main" ]]; then
  echo "Publishing is permitted only from main." >&2
  exit 1
fi

require_staged_paths() {
  local repository_root="$1"
  shift
  local actual expected
  actual="$(git -C "$repository_root" diff --cached --name-only | LC_ALL=C sort)"
  expected="$(printf '%s\n' "$@" | LC_ALL=C sort)"
  [[ "$actual" == "$expected" ]] || {
    echo "Unexpected staged paths." >&2
    echo "Expected:" >&2
    printf '%s\n' "$expected" >&2
    echo "Actual:" >&2
    printf '%s\n' "$actual" >&2
    exit 1
  }
}

export START_EPOCH="$(date +%s)"
RUN_STAMP="$(date -u +%Y-%m-%dT%H%M%SZ)"
SHORT_RUN_ID="${GITHUB_RUN_ID: -8}"
export SNAPSHOT_ID="${RUN_STAMP}-${SHORT_RUN_ID}-${GITHUB_RUN_ATTEMPT}"
export SNAPSHOT_PATH="snapshots/${SNAPSHOT_ID}"
export STAGING_ROOT="$RUNNER_TEMP/iteration-16-staging"
export STAGED_SNAPSHOT="$STAGING_ROOT/$SNAPSHOT_PATH"
export PUBLISH_ROOT="$RUNNER_TEMP/iteration-16-publish"
export ARTIFACT_ROOT="$RUNNER_TEMP/iteration-16-artifact"

{
  echo "SNAPSHOT_ID=$SNAPSHOT_ID"
  echo "SNAPSHOT_PATH=$SNAPSHOT_PATH"
  echo "ARTIFACT_ROOT=$ARTIFACT_ROOT"
} >> "$GITHUB_ENV"

mkdir -p "$STAGED_SNAPSHOT" "$ARTIFACT_ROOT"

python -m scripts.collect_market_window \
  --output "$STAGED_SNAPSHOT/market_prices.csv" \
  --receipt-output "$STAGED_SNAPSHOT/collection_receipt.json" \
  | tee "$STAGING_ROOT/collector_output.json"

TODAY_NY="$(TZ=America/New_York date +%F)"
python -m scripts.validate_market_contract \
  --csv "$STAGED_SNAPSHOT/market_prices.csv" \
  --today "$TODAY_NY"

python - <<'PY'
import json
import os
from pathlib import Path

receipt = json.loads(
    (Path(os.environ["STAGED_SNAPSHOT"]) / "collection_receipt.json").read_text(encoding="utf-8")
)
if receipt["row_count"] <= 0:
    raise SystemExit("refusing to publish an unexpected zero-row collection")
if receipt["symbol_count"] != 11 or len(receipt["required_symbols"]) != 11:
    raise SystemExit("refusing to publish an incomplete required-symbol collection")
if receipt["synthetic_prices_used"] or receipt["source_data_modified"]:
    raise SystemExit("refusing to publish synthetic or modified market data")
if not receipt["corporate_action_adjusted"] or not receipt["regular_session_only"]:
    raise SystemExit("refusing to publish data outside the frozen adjustment/session contract")
PY

git fetch --no-tags origin "$DATA_BRANCH:refs/remotes/origin/$DATA_BRANCH"
export PREVIOUS_PUBLISHED_HEAD="$(git rev-parse "refs/remotes/origin/$DATA_BRANCH")"
git worktree add --detach "$PUBLISH_ROOT" "$PREVIOUS_PUBLISHED_HEAD"
git -C "$PUBLISH_ROOT" config user.name "github-actions-market-publisher"
git -C "$PUBLISH_ROOT" config user.email "github-actions-market-publisher@users.noreply.github.com"
mkdir -p "$PUBLISH_ROOT/$SNAPSHOT_PATH"
cp "$STAGED_SNAPSHOT/market_prices.csv" "$PUBLISH_ROOT/$SNAPSHOT_PATH/market_prices.csv"
cp "$STAGED_SNAPSHOT/collection_receipt.json" "$PUBLISH_ROOT/$SNAPSHOT_PATH/collection_receipt.json"

git -C "$PUBLISH_ROOT" add -- \
  "$SNAPSHOT_PATH/market_prices.csv" \
  "$SNAPSHOT_PATH/collection_receipt.json"
require_staged_paths \
  "$PUBLISH_ROOT" \
  "$SNAPSHOT_PATH/market_prices.csv" \
  "$SNAPSHOT_PATH/collection_receipt.json"
git -C "$PUBLISH_ROOT" commit -m "data(iteration-16): publish $SNAPSHOT_ID"
export DATA_COMMIT="$(git -C "$PUBLISH_ROOT" rev-parse HEAD)"

python -m scripts.build_market_manifest \
  --data-file "$PUBLISH_ROOT/$SNAPSHOT_PATH/market_prices.csv" \
  --data-file-path "$SNAPSHOT_PATH/market_prices.csv" \
  --provider-name "Yahoo Finance chart API" \
  --source-repository "$GITHUB_REPOSITORY" \
  --source-commit-sha "$DATA_COMMIT" \
  --output "$PUBLISH_ROOT/$SNAPSHOT_PATH/market_artifact_manifest.json" \
  --notes "Validated public Iteration 16 market-data publication." \
  --today "$TODAY_NY"
python -m scripts.validate_market_contract \
  --manifest "$PUBLISH_ROOT/$SNAPSHOT_PATH/market_artifact_manifest.json" \
  --market-root "$PUBLISH_ROOT" \
  --today "$TODAY_NY"

git -C "$PUBLISH_ROOT" add -- "$SNAPSHOT_PATH/market_artifact_manifest.json"
require_staged_paths "$PUBLISH_ROOT" "$SNAPSHOT_PATH/market_artifact_manifest.json"
git -C "$PUBLISH_ROOT" commit -m "manifest(iteration-16): publish $SNAPSHOT_ID"
export PUBLIC_COMMIT="$(git -C "$PUBLISH_ROOT" rev-parse HEAD)"

python -m scripts.validate_market_artifact \
  --repository-root "$PUBLISH_ROOT" \
  --snapshot-path "$SNAPSHOT_PATH" \
  --data-commit "$DATA_COMMIT" \
  --public-commit "$PUBLIC_COMMIT" \
  --today "$TODAY_NY"

python -m scripts.build_latest_pointer \
  --repository-root "$PUBLISH_ROOT" \
  --snapshot-path "$SNAPSHOT_PATH" \
  --data-commit "$DATA_COMMIT" \
  --public-commit "$PUBLIC_COMMIT" \
  --output "$RUNNER_TEMP/latest.json" \
  --today "$TODAY_NY"
python -m scripts.validate_market_contract \
  --latest "$RUNNER_TEMP/latest.json" \
  --today "$TODAY_NY"
cp "$RUNNER_TEMP/latest.json" "$PUBLISH_ROOT/latest.json"

git -C "$PUBLISH_ROOT" add -- latest.json
require_staged_paths "$PUBLISH_ROOT" latest.json
git -C "$PUBLISH_ROOT" commit -m "pointer(iteration-16): publish $SNAPSHOT_ID"
export POINTER_COMMIT="$(git -C "$PUBLISH_ROOT" rev-parse HEAD)"

python -m scripts.verify_publication_transaction \
  --repository-root "$PUBLISH_ROOT" \
  --previous-head "$PREVIOUS_PUBLISHED_HEAD" \
  --data-commit "$DATA_COMMIT" \
  --public-commit "$PUBLIC_COMMIT" \
  --pointer-commit "$POINTER_COMMIT" \
  --snapshot-path "$SNAPSHOT_PATH" \
  --latest-file "$PUBLISH_ROOT/latest.json" \
  --today "$TODAY_NY"

# This is intentionally the only push. A failure above leaves the remote branch unchanged.
git -C "$PUBLISH_ROOT" push origin "HEAD:refs/heads/$DATA_BRANCH"
git fetch --no-tags origin "$DATA_BRANCH:refs/remotes/origin/$DATA_BRANCH"
export REMOTE_PUBLISHED_HEAD="$(git rev-parse "refs/remotes/origin/$DATA_BRANCH")"
[[ "$REMOTE_PUBLISHED_HEAD" == "$POINTER_COMMIT" ]]

mkdir -p "$ARTIFACT_ROOT/$SNAPSHOT_PATH"
cp "$PUBLISH_ROOT/$SNAPSHOT_PATH/market_prices.csv" "$ARTIFACT_ROOT/$SNAPSHOT_PATH/market_prices.csv"
cp "$PUBLISH_ROOT/$SNAPSHOT_PATH/collection_receipt.json" "$ARTIFACT_ROOT/$SNAPSHOT_PATH/collection_receipt.json"
cp "$PUBLISH_ROOT/$SNAPSHOT_PATH/market_artifact_manifest.json" "$ARTIFACT_ROOT/$SNAPSHOT_PATH/market_artifact_manifest.json"
cp "$PUBLISH_ROOT/latest.json" "$ARTIFACT_ROOT/latest.json"

python - <<'PY'
import csv
import json
import os
import time
from pathlib import Path

snapshot = Path(os.environ["PUBLISH_ROOT"]) / os.environ["SNAPSHOT_PATH"]
receipt = json.loads((snapshot / "collection_receipt.json").read_text(encoding="utf-8"))
with (snapshot / "market_prices.csv").open(newline="", encoding="utf-8") as handle:
    rows = list(csv.DictReader(handle))
keys = [(row["canonical_ticker"], row["session_date"]) for row in rows]
report = {
    "workflow_run_id": os.environ["GITHUB_RUN_ID"],
    "workflow_run_attempt": os.environ["GITHUB_RUN_ATTEMPT"],
    "source_commit": os.environ["GITHUB_SHA"],
    "publication_branch": os.environ["DATA_BRANCH"],
    "snapshot_path": os.environ["SNAPSHOT_PATH"],
    "previous_published_head": os.environ["PREVIOUS_PUBLISHED_HEAD"],
    "data_commit": os.environ["DATA_COMMIT"],
    "public_commit": os.environ["PUBLIC_COMMIT"],
    "pointer_commit": os.environ["POINTER_COMMIT"],
    "remote_published_head": os.environ["REMOTE_PUBLISHED_HEAD"],
    "runtime_seconds": int(time.time()) - int(os.environ["START_EPOCH"]),
    "api_request_count": receipt["request_count"],
    "row_count": receipt["row_count"],
    "symbol_count": receipt["symbol_count"],
    "actual_start_date": receipt["actual_start_date"],
    "actual_end_date": receipt["actual_end_date"],
    "actual_end_date_all_symbols": receipt["actual_end_date_all_symbols"],
    "duplicate_count": len(keys) - len(set(keys)),
    "target_window_complete": receipt["target_window_complete"],
    "validation_result": "passed",
    "published_to_repository": True,
}
artifact_root = Path(os.environ["ARTIFACT_ROOT"])
(artifact_root / "run_report.json").write_text(
    json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
)
summary = [
    "## Iteration 16 immutable publication",
    "",
    "| Metric | Value |",
    "|---|---:|",
]
summary.extend(f"| {key} | {value} |" for key, value in report.items())
Path(os.environ["GITHUB_STEP_SUMMARY"]).write_text("\n".join(summary) + "\n", encoding="utf-8")
print(json.dumps(report, sort_keys=True))
PY
