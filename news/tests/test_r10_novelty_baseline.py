from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "news/config/r10_novelty_baseline.json"
WORKFLOW = ROOT / ".github/workflows/verify-primary-source-coverage.yml"


class R10NoveltyBaselineTests(unittest.TestCase):
    def test_baseline_is_exact_accepted_period_four_identity(self) -> None:
        value = json.loads(CONFIG.read_text(encoding="utf-8"))
        self.assertEqual(value["schema_version"], "1.0.0")
        self.assertEqual(value["sequence"], 4)
        self.assertEqual(value["run_id"], "29740868842")
        self.assertEqual(value["run_attempt"], 1)
        self.assertEqual(value["head_sha"], "c698285901ec2ab412b5c8f59678d2bdd6a07872")
        self.assertEqual(value["artifact_name"], "ppi-primary-source-coverage-29740868842-1")
        self.assertEqual(value["artifact_sha256"], "50e5053c397ce89d72f763d2c009cf6cec6e81607d89e3ddcb973087a459b39f")
        self.assertEqual(value["identity_count"], 62)
        self.assertEqual(value["identity_set_sha256"], "eab88e001175fd2bc96173239bbeba4a7d2c6aa6e2d1adb3902cdfc938394f0c")
        self.assertEqual(value["repository"], "poudlesuman32-star/ai-market-news")

    def test_verification_uses_baseline_before_receipt_and_dispatch(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        runtime = text.split("      - name: Confirm read-only boundary", 1)[0]
        load = runtime.index("Load exact accepted R10 novelty baseline identity")
        materialize = runtime.index("Materialize exact accepted R10 novelty baseline")
        receipt = runtime.index("Build timestamp-independent source-period receipt")
        dispatch = runtime.index("Dispatch exact successful run to private source-period validator")
        self.assertLess(load, materialize)
        self.assertLess(materialize, receipt)
        self.assertLess(receipt, dispatch)
        for required in (
            "news/config/r10_novelty_baseline.json",
            "BASELINE_RUN_ID",
            "BASELINE_ARTIFACT_NAME",
            "BASELINE_ARTIFACT_SHA256",
            "BASELINE_IDENTITY_COUNT",
            "BASELINE_IDENTITY_SET_SHA256",
            "source-verification/baseline/records/news.jsonl",
        ):
            self.assertIn(required, runtime)
        self.assertNotIn("public-news-data:latest.json", runtime)
        self.assertNotIn("git fetch --no-tags origin public-news-data", runtime)

    def test_baseline_access_and_retention_are_bounded(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("permissions:\n  contents: read\n  actions: read", text)
        self.assertIn("retention-days: 90", text)
        self.assertIn("persist-credentials: false", text)
        self.assertIn("Confirm read-only boundary", text)


if __name__ == "__main__":
    unittest.main()
