import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "collect-iteration-16-market.yml"


class PublishingWorkflowSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = WORKFLOW.read_text(encoding="utf-8")
        cls.lower = cls.text.lower()

    def test_manual_trigger_only(self):
        self.assertIn("workflow_dispatch:", self.text)
        self.assertNotIn("schedule:", self.lower)
        self.assertNotIn("pull_request:", self.lower)
        self.assertNotIn("\n  push:", self.lower)

    def test_write_token_is_narrow_and_main_only(self):
        self.assertIn("contents: write", self.text)
        self.assertIn('test "$GITHUB_REF" = "refs/heads/main"', self.text)
        self.assertIn("DATA_BRANCH: iteration-16-market-data", self.text)
        self.assertNotIn("secrets.", self.lower)
        self.assertNotIn("contents: read", self.text)

    def test_unique_same_day_snapshot_ids(self):
        self.assertIn("%Y-%m-%dT%H%M%SZ", self.text)
        self.assertIn("GITHUB_RUN_ID", self.text)
        self.assertIn("GITHUB_RUN_ATTEMPT", self.text)
        self.assertIn('SNAPSHOT_PATH="snapshots/${SNAPSHOT_ID}"', self.text)

    def test_collection_is_validated_before_git_commits(self):
        collect = self.text.index("Collect live market data into staging")
        validate = self.text.index("Validate staged CSV and receipt")
        prepare = self.text.index("Prepare publication worktree")
        commit_a = self.text.index("Create Commit A")
        self.assertLess(collect, validate)
        self.assertLess(validate, prepare)
        self.assertLess(prepare, commit_a)
        self.assertIn("row_count", self.text)
        self.assertIn("symbol_count", self.text)
        self.assertIn("synthetic_prices_used", self.text)

    def test_three_commit_transaction_is_verified_before_one_push(self):
        commit_a = self.text.index("Create Commit A")
        commit_b = self.text.index("Create Commit B")
        commit_c = self.text.index("Create Commit C")
        verify = self.text.index("Verify complete publication transaction")
        push = self.text.index("Publish transaction with one fast-forward push")
        self.assertLess(commit_a, commit_b)
        self.assertLess(commit_b, commit_c)
        self.assertLess(commit_c, verify)
        self.assertLess(verify, push)
        self.assertEqual(self.lower.count('git -c "$publish_root" push'), 1)
        self.assertNotIn("--force", self.lower)
        self.assertIn("python -m scripts.verify_publication_transaction", self.text)

    def test_previous_snapshot_is_preserved_by_fast_forward_only(self):
        self.assertIn('PREVIOUS_PUBLISHED_HEAD="$(git rev-parse "origin/$DATA_BRANCH")"', self.text)
        self.assertIn('git worktree add --detach "$PUBLISH_ROOT" "$PREVIOUS_PUBLISHED_HEAD"', self.text)
        self.assertIn('HEAD:refs/heads/$DATA_BRANCH', self.text)
        self.assertIn('test "$REMOTE_PUBLISHED_HEAD" = "$POINTER_COMMIT"', self.text)

    def test_artifact_and_runtime_limits(self):
        self.assertIn("runs-on: ubuntu-latest", self.text)
        self.assertIn("timeout-minutes: 15", self.text)
        self.assertIn("retention-days: 3", self.text)
        self.assertIn("if-no-files-found: error", self.text)
        self.assertIn('"published_to_repository": True', self.text)


if __name__ == "__main__":
    unittest.main()
