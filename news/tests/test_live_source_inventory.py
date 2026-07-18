from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class LiveSourceInventoryTests(unittest.TestCase):
    def test_all_sec_entities_have_reviewed_official_source_inventory(self) -> None:
        company = json.loads(
            (ROOT / "news/config/official_company_sources.json").read_text(encoding="utf-8")
        )
        sec = json.loads((ROOT / "news/config/sec_companies.json").read_text(encoding="utf-8"))

        active_by_ticker = {str(source["ticker"]): source for source in company["sources"]}
        retired = company.get("retired_sources", [])
        retired_by_ticker = {str(source["ticker"]): source for source in retired}
        sec_tickers = {str(source["ticker"]) for source in sec["companies"]}

        self.assertEqual(set(active_by_ticker), {"AAPL", "MU", "NVDA"})
        self.assertEqual(set(active_by_ticker), sec_tickers)
        self.assertEqual(active_by_ticker["MU"]["source_kind"], "html_release_index")
        self.assertEqual(
            active_by_ticker["MU"]["index_url"],
            "https://investors.micron.com/latest-news-english",
        )
        self.assertEqual(active_by_ticker["MU"]["allowed_hosts"], ["micron.com"])

        self.assertIn("MU", retired_by_ticker)
        self.assertIn("rss/news-releases.xml", retired_by_ticker["MU"]["feed_url"])
        self.assertIn("Replaced", retired_by_ticker["MU"]["reason"])


if __name__ == "__main__":
    unittest.main()
