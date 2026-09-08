from pathlib import Path
import unittest


class ImmutableSnapshotReviewBridgeTests(unittest.TestCase):
    def test_bridge_is_exact_zero_provider_and_review_only(self) -> None:
        text = Path(
            ".github/workflows/ppi-immutable-snapshot-review-bridge.yml"
        ).read_text(encoding="utf-8")

        self.assertIn("actions: write", text)
        self.assertIn("contents: read", text)
        self.assertIn("ppi-stable-instrument-id-allocation-artifact-review.yml", text)
        self.assertIn("ppi-immutable-universe-snapshot-pilot.yml", text)
        self.assertIn("ppi-immutable-universe-snapshot-artifact-review.yml", text)
        self.assertIn("status=success", text)
        self.assertIn("workflow_dispatch", text)
        self.assertIn(".expired == false", text)
        self.assertIn("PPI-IMMUTABLE-UNIVERSE-SNAPSHOT-PILOT-001-R1", text)
        self.assertIn("candidate_count", text)
        self.assertIn("unresolved_asset_subtype", text)
        self.assertIn("network_requests_performed", text)
        self.assertIn("private_access", text)
        self.assertIn("registry_mutation", text)
        self.assertIn("production", text)
        self.assertIn("publication", text)
        self.assertIn("trading", text)
        self.assertIn("billing_budget_mutation", text)
        self.assertIn("steps.gate.outputs.gate_passed == 'true'", text)
        self.assertIn("steps.duplicate.outputs.exists == 'false'", text)
        self.assertIn("--method POST", text)
        self.assertIn("actions/workflows/ppi-immutable-universe-snapshot-artifact-review.yml/dispatches", text)
        self.assertNotIn("gh run download", text)
        self.assertNotIn("gh workflow run", text)
        self.assertNotIn("sec.gov", text.lower())
        self.assertNotIn("openfigi.com", text.lower())
        self.assertNotIn("secrets.", text)
        self.assertNotIn("contents: write", text)
        self.assertNotIn("registry_mutation == true", text)
        self.assertNotIn("ai-signal-engine", text)

        self.assertIn("  push:\n", text)
        self.assertIn("    branches:\n      - main\n", text)
        self.assertIn(
            "    paths:\n      - .github/workflows/ppi-immutable-snapshot-review-bridge.yml\n",
            text,
        )


if __name__ == "__main__":
    unittest.main()
