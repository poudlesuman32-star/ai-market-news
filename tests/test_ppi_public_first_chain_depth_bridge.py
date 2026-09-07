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
        stable_review = Path(
            ".github/workflows/ppi-stable-instrument-id-allocation-artifact-review.yml"
        ).read_text(encoding="utf-8")

        self.assertIn("actions: write", bridge)
        self.assertIn("contents: read", bridge)
        self.assertIn(".gate_passed == true", bridge)
        self.assertIn('.artifact_mode == "success"', bridge)
        self.assertIn(".candidate_count == 500", bridge)
        self.assertIn(".authority.stable_instrument_id_allocation == false", bridge)
        self.assertIn("ppi-stable-instrument-id-allocation-pilot.yml", bridge)
        self.assertIn("steps.duplicate.outputs.exists == 'false'", bridge)
        self.assertIn("review_run_id", bridge)
        self.assertIn("review_run_attempt", bridge)

        # The bridge intentionally does not check out the repository. Artifact
        # retrieval and workflow dispatch must therefore use repository-scoped
        # Actions REST endpoints instead of gh commands that infer git context.
        self.assertNotIn("gh run download", bridge)
        self.assertNotIn("gh workflow run", bridge)
        self.assertIn("actions/runs/${REVIEW_ID}/artifacts", bridge)
        self.assertIn(".expired == false", bridge)
        self.assertIn("actions/artifacts/${artifact_id}/zip", bridge)
        self.assertIn("unzip -q review.zip -d downloaded-review", bridge)
        self.assertIn("test -f downloaded-review/review.json", bridge)
        self.assertIn("--method POST", bridge)
        self.assertIn(
            "actions/workflows/ppi-stable-instrument-id-allocation-pilot.yml/dispatches",
            bridge,
        )
        self.assertIn('{ref:"main",inputs:{review_run_id:$review_run_id,review_run_attempt:$review_run_attempt}}', bridge)
        self.assertIn("--input -", bridge)

        # A reviewed bridge change on main may self-execute once instead of relying
        # on GitHub's best-effort schedule. The push trigger must be restricted to
        # main and to this workflow file only; duplicate dispatch remains guarded.
        self.assertIn("  push:\n", bridge)
        self.assertIn("    branches:\n      - main\n", bridge)
        self.assertIn(
            "    paths:\n      - .github/workflows/ppi-public-first-chain-depth-bridge.yml\n",
            bridge,
        )

        # Successful zero-provider allocations may be handed to the independent
        # stable-ID reviewer only after the exact safe artifact is uniquely resolved.
        self.assertIn("Locate exact successful stable-ID allocation", bridge)
        self.assertIn("ppi-stable-instrument-id-allocation-pilot-${ALLOCATION_ID}-${ALLOCATION_ATTEMPT}", bridge)
        self.assertIn("PPI-STABLE-INSTRUMENT-ID-ALLOCATION-PILOT-001-R1", bridge)
        self.assertIn(".network_requests_performed == 0", bridge)
        self.assertIn(".private_access == false", bridge)
        self.assertIn(".registry_mutation == false", bridge)
        self.assertIn(".production == false", bridge)
        self.assertIn(".publication == false", bridge)
        self.assertIn(".trading == false", bridge)
        self.assertIn(".stable_instrument_ids_allocated + .ambiguous_deferred + .unmatched_deferred", bridge)
        self.assertIn(
            "Stable ID review from allocation ${ALLOCATION_ID}-${ALLOCATION_ATTEMPT} on ${GITHUB_SHA}",
            bridge,
        )
        self.assertIn("steps.review_duplicate.outputs.exists == 'false'", bridge)
        self.assertIn(
            "actions/workflows/ppi-stable-instrument-id-allocation-artifact-review.yml/dispatches",
            bridge,
        )
        self.assertIn('{ref:"main",inputs:{source_run_id:$source_run_id,source_run_attempt:$source_run_attempt}}', bridge)
        self.assertIn("run-name: Stable ID review from allocation", stable_review)
        self.assertIn("on ${{ github.sha }}", stable_review)
        self.assertIn("review_stable_instrument_id_allocation_hardened.py", stable_review)

        self.assertNotIn("sec.gov", bridge.lower())
        self.assertNotIn("openfigi.com", bridge.lower())
        self.assertNotIn("secrets.", bridge)
        self.assertNotIn("registry_mutation == true", bridge)
        self.assertNotIn("ai-signal-engine", bridge)
        self.assertIn(
            "run-name: Stable ID allocation from OpenFIGI review",
            stable,
        )


if __name__ == "__main__":
    unittest.main()
