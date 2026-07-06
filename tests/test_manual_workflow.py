import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "collect-iteration-16-market.yml"


class ManualWorkflowSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = WORKFLOW.read_text(encoding="utf-8")
        cls.lower = cls.text.lower()

    def test_manual_trigger_only(self):
        self.assertIn("workflow_dispatch:", self.text)
        self.assertNotIn("schedule:", self.lower)
        self.assertNotIn("pull_request:", self.lower)
        self.assertNotIn("\n  push:", self.lower)

    def test_read_only_token_and_no_persistent_credentials(self):
        self.assertIn("contents: read", self.text)
        self.assertIn("persist-credentials: false", self.text)
        self.assertNotIn("contents: write", self.text)
        self.assertNotIn("git push", self.lower)
        self.assertNotIn("secrets.", self.lower)

    def test_runtime_and_artifact_limits(self):
        self.assertIn("runs-on: ubuntu-latest", self.text)
        self.assertIn("timeout-minutes: 15", self.text)
        self.assertIn("retention-days: 3", self.text)
        self.assertIn("if-no-files-found: error", self.text)

    def test_required_validation_stages_are_present(self):
        for command in (
            "python -m unittest discover -s tests -v",
            "scripts/collect_market_window.py",
            "scripts/validate_market_contract.py",
            "scripts/build_market_manifest.py",
            "scripts/validate_market_artifact.py",
        ):
            self.assertIn(command, self.text)

    def test_preview_only_and_exact_snapshot_validation(self):
        self.assertIn("published_to_repository\": False", self.text)
        self.assertIn("git checkout --detach", self.text)
        self.assertIn("collector_output.json", self.text)
        self.assertNotIn("$SNAPSHOT_PATH/collector_output.json", self.text)
        self.assertIn("$SNAPSHOT_PATH/market_prices.csv", self.text)
        self.assertIn("$SNAPSHOT_PATH/collection_receipt.json", self.text)
        self.assertIn("$SNAPSHOT_PATH/market_artifact_manifest.json", self.text)


if __name__ == "__main__":
    unittest.main()
