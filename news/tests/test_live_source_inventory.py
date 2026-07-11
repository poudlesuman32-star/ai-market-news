from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class LiveSourceInventoryTests(unittest.TestCase):
    def test_unhealthy_company_feed_is_explicitly_disabled_without_losing_sec_coverage(self) -> None:
        company = json.loads(
            (ROOT / "news/config/official_company_sources.json").read_text(encoding="utf-8")
        )
        sec = json.loads((ROOT / "news/config/sec_companies.json").read_text(encoding="utf-8"))

        active_company_tickers = {str(source["ticker"]) for source in company["sources"]}
        disabled = company.get("disabled_sources", [])
        disabled_by_ticker = {str(source["ticker"]): source for source in disabled}
        sec_tickers = {str(source["ticker"]) for source in sec["companies"]}

        self.assertEqual(active_company_tickers, {"AAPL", "NVDA"})
        self.assertIn("MU", disabled_by_ticker)
        self.assertIn("MU", sec_tickers)
        self.assertIn("29138091476", disabled_by_ticker["MU"]["reason"])
        self.assertIn("zero failures", disabled_by_ticker["MU"]["re_enable_requires"])

        self.assertTrue(active_company_tickers.isdisjoint(disabled_by_ticker))
        self.assertTrue(active_company_tickers.issubset(sec_tickers))
        self.assertTrue(set(disabled_by_ticker).issubset(sec_tickers))


if __name__ == "__main__":
    unittest.main()
