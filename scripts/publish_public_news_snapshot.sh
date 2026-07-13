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
: "${NEWS_FILE:?NEWS_FILE is required}"
: "${COLLECTION_RECEIPT_FILE:?COLLECTION_RECEIPT_FILE is required}"

DATA_BRANCH="${DATA_BRANCH:-public-news-data}"
GATE_FILE="${GATE_FILE:-news/config/public_news_preview_gate.json}"
export DATA_BRANCH

if [[ "$GITHUB_REF" != "refs/heads/main" ]]; then
  echo "Publishing is permitted only from main." >&2
  exit 1
fi
if [[ "$GITHUB_REPOSITORY" != "poudlesuman32-star/ai-market-news" ]]; then
  echo "Unexpected source repository." >&2
  exit 1
fi
if [[ "$DATA_BRANCH" != "public-news-data" ]]; then
  echo "Public news may publish only to public-news-data." >&2
  exit 1
fi

PYTHONPATH="${PYTHONPATH:-news/src}" python -m ai_market_news.preview_gate \
  require-publication --gate "$GATE_FILE"

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
export PUBLISH_ROOT="$RUNNER_TEMP/public-news-publish"
export ARTIFACT_ROOT="$RUNNER_TEMP/public-news-publication-artifact"
export PUBLICATION_REUSED="false"

[[ -s "$NEWS_FILE" ]] || { echo "news.jsonl is empty or missing" >&2; exit 1; }
[[ -s "$COLLECTION_RECEIPT_FILE" ]] || { echo "collection_receipt.json is empty or missing" >&2; exit 1; }

# Validate the exact candidate files before any branch mutation or resume decision.
PYTHONPATH="${PYTHONPATH:-news/src}" python - <<'PY'
import json
import os
from pathlib import Path

from ai_market_news.build_preview_artifacts import load_news, sha256_file
from ai_market_news.collector_common import require

news = Path(os.environ["NEWS_FILE"])
receipt_path = Path(os.environ["COLLECTION_RECEIPT_FILE"])
records = load_news(news)
require(bool(records), "refusing to publish a zero-event dataset")
receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
require(receipt.get("collection_complete") is True, "receipt is incomplete")
require(receipt.get("dataset_sha256") == sha256_file(news), "receipt hash mismatch")
require(receipt.get("record_count") == len(records), "receipt record count mismatch")
require(receipt.get("synthetic_content_used") is False, "receipt reports synthetic content")
require(receipt.get("source_content_modified") is False, "receipt reports modified content")
require(receipt.get("private_content_excluded") is True, "receipt does not confirm private-content exclusion")
require(not receipt.get("provider_failures"), "provider failures block publication")
PY

git fetch --no-tags origin "$DATA_BRANCH:refs/remotes/origin/$DATA_BRANCH"
export REMOTE_PUBLISHED_HEAD="$(git rev-parse "refs/remotes/origin/$DATA_BRANCH")"
git worktree add --detach "$PUBLISH_ROOT" "$REMOTE_PUBLISHED_HEAD"
git -C "$PUBLISH_ROOT" config user.name "github-actions-public-news-publisher"
git -C "$PUBLISH_ROOT" config user.email "github-actions-public-news-publisher@users.noreply.github.com"

export RESOLUTION_FILE="$RUNNER_TEMP/existing-publication.json"
PYTHONPATH="${PYTHONPATH:-news/src}" python -m ai_market_news.resolve_existing_news_publication \
  --repository-root "$PUBLISH_ROOT" \
  --news "$NEWS_FILE" \
  --receipt "$COLLECTION_RECEIPT_FILE" \
  --output "$RESOLUTION_FILE"
RESOLUTION_STATUS="$(python - <<'PY'
import json
import os
from pathlib import Path

value = json.loads(Path(os.environ["RESOLUTION_FILE"]).read_text(encoding="utf-8"))
print(value["status"])
PY
)"

if [[ "$RESOLUTION_STATUS" == "found" ]]; then
  python - <<'PY' > "$RUNNER_TEMP/existing-publication.env"
import json
import os
import shlex
from pathlib import Path

value = json.loads(Path(os.environ["RESOLUTION_FILE"]).read_text(encoding="utf-8"))
for key in ("previous_head", "data_commit", "public_commit", "pointer_commit", "snapshot_path"):
    print(f"export {key.upper()}={shlex.quote(str(value[key]))}")
PY
  # The file contains only validated hashes and a validated snapshots/ path.
  source "$RUNNER_TEMP/existing-publication.env"
  rm -f "$RUNNER_TEMP/existing-publication.env"
  export SNAPSHOT_ID="${SNAPSHOT_PATH#snapshots/}"
  export PUBLICATION_REUSED="true"

  PYTHONPATH="${PYTHONPATH:-news/src}" python -m ai_market_news.verify_news_publication_transaction \
    --repository-root "$PUBLISH_ROOT" \
    --previous-head "$PREVIOUS_HEAD" \
    --data-commit "$DATA_COMMIT" \
    --public-commit "$PUBLIC_COMMIT" \
    --pointer-commit "$POINTER_COMMIT" \
    --snapshot-path "$SNAPSHOT_PATH"
elif [[ "$RESOLUTION_STATUS" == "not_found" ]]; then
  export PREVIOUS_HEAD="$REMOTE_PUBLISHED_HEAD"

  mkdir -p "$PUBLISH_ROOT/$SNAPSHOT_PATH"
  cp "$NEWS_FILE" "$PUBLISH_ROOT/$SNAPSHOT_PATH/news.jsonl"
  cp "$COLLECTION_RECEIPT_FILE" "$PUBLISH_ROOT/$SNAPSHOT_PATH/collection_receipt.json"

  git -C "$PUBLISH_ROOT" add -- \
    "$SNAPSHOT_PATH/news.jsonl" \
    "$SNAPSHOT_PATH/collection_receipt.json"
  require_staged_paths \
    "$PUBLISH_ROOT" \
    "$SNAPSHOT_PATH/news.jsonl" \
    "$SNAPSHOT_PATH/collection_receipt.json"
  git -C "$PUBLISH_ROOT" commit -m "data(public-news): publish $SNAPSHOT_ID"
  export DATA_COMMIT="$(git -C "$PUBLISH_ROOT" rev-parse HEAD)"

  PYTHONPATH="${PYTHONPATH:-news/src}" python -m ai_market_news.build_news_manifest \
    --news "$PUBLISH_ROOT/$SNAPSHOT_PATH/news.jsonl" \
    --receipt "$PUBLISH_ROOT/$SNAPSHOT_PATH/collection_receipt.json" \
    --snapshot-path "$SNAPSHOT_PATH" \
    --data-commit "$DATA_COMMIT" \
    --source-repository "$GITHUB_REPOSITORY" \
    --output "$PUBLISH_ROOT/$SNAPSHOT_PATH/news_manifest.json"

  git -C "$PUBLISH_ROOT" add -- "$SNAPSHOT_PATH/news_manifest.json"
  require_staged_paths "$PUBLISH_ROOT" "$SNAPSHOT_PATH/news_manifest.json"
  git -C "$PUBLISH_ROOT" commit -m "manifest(public-news): publish $SNAPSHOT_ID"
  export PUBLIC_COMMIT="$(git -C "$PUBLISH_ROOT" rev-parse HEAD)"

  PYTHONPATH="${PYTHONPATH:-news/src}" python -m ai_market_news.build_news_latest_pointer \
    --manifest "$PUBLISH_ROOT/$SNAPSHOT_PATH/news_manifest.json" \
    --public-commit "$PUBLIC_COMMIT" \
    --output "$PUBLISH_ROOT/latest.json"

  git -C "$PUBLISH_ROOT" add -- latest.json
  require_staged_paths "$PUBLISH_ROOT" latest.json
  git -C "$PUBLISH_ROOT" commit -m "pointer(public-news): publish $SNAPSHOT_ID"
  export POINTER_COMMIT="$(git -C "$PUBLISH_ROOT" rev-parse HEAD)"

  PYTHONPATH="${PYTHONPATH:-news/src}" python -m ai_market_news.verify_news_publication_transaction \
    --repository-root "$PUBLISH_ROOT" \
    --previous-head "$PREVIOUS_HEAD" \
    --data-commit "$DATA_COMMIT" \
    --public-commit "$PUBLIC_COMMIT" \
    --pointer-commit "$POINTER_COMMIT" \
    --snapshot-path "$SNAPSHOT_PATH"

  # This is intentionally the only push. Any failure above leaves the remote pointer unchanged.
  git -C "$PUBLISH_ROOT" push origin "HEAD:refs/heads/$DATA_BRANCH"
  git fetch --no-tags origin "$DATA_BRANCH:refs/remotes/origin/$DATA_BRANCH"
  export REMOTE_PUBLISHED_HEAD="$(git rev-parse "refs/remotes/origin/$DATA_BRANCH")"
  [[ "$REMOTE_PUBLISHED_HEAD" == "$POINTER_COMMIT" ]]
else
  echo "Unexpected publication resolution status: $RESOLUTION_STATUS" >&2
  exit 1
fi

mkdir -p "$ARTIFACT_ROOT/$SNAPSHOT_PATH"
cp "$PUBLISH_ROOT/$SNAPSHOT_PATH/news.jsonl" "$ARTIFACT_ROOT/$SNAPSHOT_PATH/news.jsonl"
cp "$PUBLISH_ROOT/$SNAPSHOT_PATH/collection_receipt.json" "$ARTIFACT_ROOT/$SNAPSHOT_PATH/collection_receipt.json"
cp "$PUBLISH_ROOT/$SNAPSHOT_PATH/news_manifest.json" "$ARTIFACT_ROOT/$SNAPSHOT_PATH/news_manifest.json"
git -C "$PUBLISH_ROOT" show "$POINTER_COMMIT:latest.json" > "$ARTIFACT_ROOT/latest.json"

# Persist all transaction identifiers for subsequent workflow steps. Shell exports do not cross step boundaries.
{
  echo "SNAPSHOT_ID=$SNAPSHOT_ID"
  echo "SNAPSHOT_PATH=$SNAPSHOT_PATH"
  echo "ARTIFACT_ROOT=$ARTIFACT_ROOT"
  echo "PREVIOUS_PUBLISHED_HEAD=$PREVIOUS_HEAD"
  echo "DATA_COMMIT=$DATA_COMMIT"
  echo "PUBLIC_COMMIT=$PUBLIC_COMMIT"
  echo "POINTER_COMMIT=$POINTER_COMMIT"
  echo "REMOTE_PUBLISHED_HEAD=$REMOTE_PUBLISHED_HEAD"
  echo "PUBLICATION_REUSED=$PUBLICATION_REUSED"
} >> "$GITHUB_ENV"

PYTHONPATH="${PYTHONPATH:-news/src}" python - <<'PY'
import json
import os
import time
from pathlib import Path

receipt = json.loads(Path(os.environ["COLLECTION_RECEIPT_FILE"]).read_text(encoding="utf-8"))
report = {
    "schema_version": "1.0.0",
    "stage": "PPI-R5",
    "phase": "immutable_publication",
    "workflow_run_id": os.environ["GITHUB_RUN_ID"],
    "workflow_run_attempt": os.environ["GITHUB_RUN_ATTEMPT"],
    "source_commit": os.environ["GITHUB_SHA"],
    "publication_branch": os.environ["DATA_BRANCH"],
    "snapshot_path": os.environ["SNAPSHOT_PATH"],
    "previous_published_head": os.environ["PREVIOUS_HEAD"],
    "data_commit": os.environ["DATA_COMMIT"],
    "public_commit": os.environ["PUBLIC_COMMIT"],
    "pointer_commit": os.environ["POINTER_COMMIT"],
    "remote_published_head": os.environ["REMOTE_PUBLISHED_HEAD"],
    "publication_reused": os.environ["PUBLICATION_REUSED"] == "true",
    "publication_push_performed": os.environ["PUBLICATION_REUSED"] != "true",
    "runtime_seconds": int(time.time()) - int(os.environ["START_EPOCH"]),
    "record_count": receipt["record_count"],
    "event_count": receipt["event_count"],
    "provider_counts": receipt["provider_counts"],
    "ticker_count": len(receipt["tickers"]),
    "validation_result": "passed",
    "published_to_repository": True,
    "synthetic_content_used": False,
    "source_content_modified": False,
    "private_content_excluded": True,
}
artifact_root = Path(os.environ["ARTIFACT_ROOT"])
artifact_root.mkdir(parents=True, exist_ok=True)
(artifact_root / "run_report.json").write_text(
    json.dumps(report, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
summary = [
    "## PPI-R5 immutable public-news publication",
    "",
    "| Metric | Value |",
    "|---|---|",
]
summary.extend(f"| {key} | {value} |" for key, value in report.items())
Path(os.environ["GITHUB_STEP_SUMMARY"]).write_text("\n".join(summary) + "\n", encoding="utf-8")
print(json.dumps(report, sort_keys=True))
PY
