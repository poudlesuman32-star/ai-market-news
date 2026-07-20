from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "news/config/r10_novelty_baseline.json"
WORKFLOW = ROOT / ".github/workflows/verify-primary-source-coverage.yml"


class R10NoveltyBaselineTests(unittest.TestCase):
    def test_baseline_is_exact_accepted_period_three_identity(self) -> None:
        value = json.loads(CONFIG.read_text(encoding="utf-8"))
        self.assertEqual(
            value,
            {
                "schema_version": "1.0.0",
                "sequence": 3,
                "run_id": "29648125982",
                "run_attempt": 1,
                "head_sha": "50ae571374a3c9ffd92cdcf007bfcc5a3e48a875",
                "artifact_name": "ppi-primary-source-coverage-29648125982-1",
                "artifact_sha256": "3ebde779d293a86b481418483c694fb447dd7c92e3891fafd12dde604a68e489",
                "identity_count": 65,
                "identity_set_sha256": "9e5c6cc191ddfa4614cea6f2addee953d81936be39639369e70ea221ea7c8a18",
                "repository": "poudlesuman32-star/ai-market-news",
            },
        )

    def test_verification_uses_exact_baseline_artifact_not_published_snapshot(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        materialize = text.index("Materialize exact accepted R10 novelty baseline")
        receipt = text.index("Build timestamp-independent source-period receipt")
        dispatch = text.index("Dispatch exact successful run to private source-period validator")
        self.assertLess(materialize, receipt)
        self.assertLess(receipt, dispatch)
        self.assertIn("R10_NOVELTY_BASELINE_CONFIG: news/config/r10_novelty_baseline.json", text)
        self.assertIn('gh run download "$BASELINE_RUN_ID"', text)
        self.assertIn('--previous source-verification/baseline/records/news.jsonl', text)
        self.assertIn('matches[0].get("digest") == "sha256:" + os.environ["BASELINE_ARTIFACT_SHA256"]', text)
        self.assertIn('content_fingerprint(keys) == os.environ["BASELINE_IDENTITY_SET_SHA256"]', text)
        self.assertNotIn("public-news-data:latest.json", text)
        self.assertNotIn("git fetch --no-tags origin public-news-data", text)

    def test_baseline_access_and_retention_are_bounded(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("permissions:\n  contents: read\n  actions: read", text)
        self.assertIn("retention-days: 90", text)
        self.assertNotIn("contents: write", text)
        self.assertNotIn("pull-requests: write", text)
        self.assertNotIn("git push", text)
        self.assertNotIn("gh pr create", text)
        self.assertNotIn("gh pr merge", text)


if __name__ == "__main__":
    unittest.main()
