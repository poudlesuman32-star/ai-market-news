from pathlib import Path
import unittest


class ChainDepthBridgeTests(unittest.TestCase):
    def test_bridge_is_fail_closed_and_provider_free(self):
        bridge = Path(
            ".github/workflows/ppi-public-first-chain-depth-bridge.yml"
        ).read_text(encoding="utf-8")
        stable = Path(
            ".github/workflows/ppi-stable-instrument-id-allocation-pilot.yml"
        ).read_text(encoding="utf-8")

        self.assertIn("actions: write", bridge)
        self.assertIn("contents: read", bridge)
        self.assertIn(".gate_passed == true", bridge)
        self.assertIn('.artifact_mode == "success"', bridge)
        self.assertIn(".candidate_count == 500", bridge)
        self.assertIn(".authority.stable_instrument_id_allocation == false", bridge)
        self.assertIn("ppi-stable-instrument-id-allocation-pilot.yml", bridge)
        self.assertIn("steps.duplicate.outputs.exists == 'false'", bridge)
        self.assertIn("review_run_id=\"$REVIEW_ID\"", bridge)
        self.assertIn("review_run_attempt=\"$REVIEW_ATTEMPT\"", bridge)
        self.assertNotIn("sec.gov", bridge.lower())
        self.assertNotIn("openfigi.com", bridge.lower())
        self.assertNotIn("secrets.", bridge)
        self.assertNotIn("registry", bridge.lower())
        self.assertNotIn("ai-signal-engine", bridge)
        self.assertIn(
            "run-name: Stable ID allocation from OpenFIGI review",
            stable,
        )


if __name__ == "__main__":
    unittest.main()
