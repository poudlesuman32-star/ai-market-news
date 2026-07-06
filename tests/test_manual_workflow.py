import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "collect-iteration-16-market.yml"
PUBLISHER = ROOT / "scripts" / "publish_market_snapshot.sh"


class PublishingWorkflowSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")
        cls.publisher = PUBLISHER.read_text(encoding="utf-8")
        cls.combined = cls.workflow + "\n" + cls.publisher
        cls.workflow_lower = cls.workflow.lower()
        cls.publisher_lower = cls.publisher.lower()

    def test_manual_trigger_only(self):
        self.assertIn("workflow_dispatch:", self.workflow)
        self.assertNotIn("schedule:", self.workflow_lower)
        self.assertNotIn("pull_request:", self.workflow_lower)
        self.assertNotIn("\n  push:", self.workflow_lower)

    def test_write_token_is_narrow_and_main_only(self):
        self.assertIn("contents: write", self.workflow)
        self.assertIn('test "$GITHUB_REF" = "refs/heads/main"', self.workflow)
        self.assertIn("DATA_BRANCH: iteration-16-market-data", self.workflow)
        self.assertNotIn("secrets.", self.combined.lower())
        self.assertNotIn("contents: read", self.workflow)

    def test_unique_same_day_snapshot_ids(self):
        self.assertIn("%Y-%m-%dT%H%M%SZ", self.publisher)
        self.assertIn("GITHUB_RUN_ID", self.publisher)
        self.assertIn("GITHUB_RUN_ATTEMPT", self.publisher)
        self.assertIn('SNAPSHOT_PATH="snapshots/${SNAPSHOT_ID}"', self.publisher)

    def test_collection_is_validated_before_git_commits(self):
        collect = self.publisher.index("scripts.collect_market_window")
        validate = self.publisher.index("scripts.validate_market_contract")
        worktree = self.publisher.index("git worktree add")
        commit_a = self.publisher.index('commit -m "data(iteration-16)')
        self.assertLess(collect, validate)
        self.assertLess(validate, worktree)
        self.assertLess(worktree, commit_a)
        self.assertIn('receipt["row_count"] <= 0', self.publisher)
        self.assertIn('receipt["symbol_count"] != 11', self.publisher)
        self.assertIn('receipt["synthetic_prices_used"]', self.publisher)

    def test_three_commit_transaction_is_verified_before_one_push(self):
        commit_a = self.publisher.index('commit -m "data(iteration-16)')
        commit_b = self.publisher.index('commit -m "manifest(iteration-16)')
        commit_c = self.publisher.index('commit -m "pointer(iteration-16)')
        verify = self.publisher.index("scripts.verify_publication_transaction")
        push = self.publisher.index('git -C "$PUBLISH_ROOT" push')
        self.assertLess(commit_a, commit_b)
        self.assertLess(commit_b, commit_c)
        self.assertLess(commit_c, verify)
        self.assertLess(verify, push)
        self.assertEqual(self.publisher_lower.count('git -c "$publish_root" push'), 1)
        self.assertNotIn("--force", self.publisher_lower)

    def test_previous_snapshot_is_preserved_by_fast_forward_only(self):
        self.assertIn('PREVIOUS_PUBLISHED_HEAD="$(git rev-parse "refs/remotes/origin/$DATA_BRANCH")"', self.publisher)
        self.assertIn('git worktree add --detach "$PUBLISH_ROOT" "$PREVIOUS_PUBLISHED_HEAD"', self.publisher)
        self.assertIn('HEAD:refs/heads/$DATA_BRANCH', self.publisher)
        self.assertIn('[[ "$REMOTE_PUBLISHED_HEAD" == "$POINTER_COMMIT" ]]', self.publisher)

    def test_wrapper_runs_tests_before_publisher(self):
        unit_tests = self.workflow.index("python -m unittest discover -s tests -v")
        publisher = self.workflow.index("bash scripts/publish_market_snapshot.sh")
        self.assertLess(unit_tests, publisher)
        self.assertIn("set -euo pipefail", self.publisher)

    def test_artifact_and_runtime_limits(self):
        self.assertIn("runs-on: ubuntu-latest", self.workflow)
        self.assertIn("timeout-minutes: 15", self.workflow)
        self.assertIn("retention-days: 3", self.workflow)
        self.assertIn("if-no-files-found: error", self.workflow)
        self.assertIn('"published_to_repository": True', self.publisher)


if __name__ == "__main__":
    unittest.main()
