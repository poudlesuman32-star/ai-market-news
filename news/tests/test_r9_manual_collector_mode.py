from __future__ import annotations

import unittest
from pathlib import Path


class R9ManualCollectorModeTests(unittest.TestCase):
    def test_live_collector_is_manual_only(self) -> None:
        workflow = Path(".github/workflows/collect-public-news-live-auto.yml").read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", workflow)
        self.assertNotIn("schedule:", workflow)
        self.assertNotIn("cron:", workflow)
        self.assertIn("cancel-in-progress: false", workflow)
        self.assertIn("contents: read", workflow)


if __name__ == "__main__":
    unittest.main()
