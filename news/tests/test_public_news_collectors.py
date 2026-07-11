from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from ai_market_news.collect_company_releases import collect_company_release_fixture, main as company_main
from ai_market_news.collect_sec import collect_sec_fixture, main as sec_main
from ai_market_news.collector_common import CollectorError


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).resolve().parent / "fixtures"
COLLECTED_AT = "2026-07-10T18:00:00Z"
FORBIDDEN_FIELDS = {
    "score",
    "rank",
    "portfolio",
    "watchlist",
    "recommendation",
    "position_size",
    "credentials",
    "api_key",
    "private_notes",
}


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class PublicNewsCollectorTests(unittest.TestCase):
    def assert_public_record(self, record: dict) -> None:
        self.assertEqual(len(record["record_id"]), 64)
        self.assertEqual(len(record["event_id"]), 64)
        self.assertEqual(len(record["source_hash"]), 64)
        self.assertEqual(record["duplicate_group_id"], record["event_id"])
        self.assertTrue(record["primary_source"])
        self.assertEqual(record["validation"], "collected_untransformed")
        self.assertEqual(record["catalyst_tags"], [])
        self.assertEqual(record["ai_infrastructure_layers"], [])
        self.assertFalse(record["synthetic_content_used"])
        self.assertFalse(record["source_content_modified"])
        self.assertTrue(record["source_url"].startswith("https://"))
        self.assertFalse(FORBIDDEN_FIELDS.intersection(record))

    def test_sec_collection_is_deterministic_and_public_only(self) -> None:
        payload = load_fixture("sec_filings.json")
        first = collect_sec_fixture(payload, collected_at_utc=COLLECTED_AT)
        second = collect_sec_fixture(payload, collected_at_utc=COLLECTED_AT)
        self.assertEqual(first, second)
        self.assertEqual([row["ticker"] for row in first], ["AAPL", "NVDA"])
        self.assertTrue(all(row["source_type"] == "sec_filing" for row in first))
        self.assertTrue(all(row["provider"] == "sec_edgar" for row in first))
        self.assertTrue(all(row["filing_type"] for row in first))
        for record in first:
            self.assert_public_record(record)

    def test_company_release_collection_is_deterministic_and_public_only(self) -> None:
        payload = load_fixture("company_releases.json")
        first = collect_company_release_fixture(payload, collected_at_utc=COLLECTED_AT)
        second = collect_company_release_fixture(payload, collected_at_utc=COLLECTED_AT)
        self.assertEqual(first, second)
        self.assertEqual([row["ticker"] for row in first], ["NVDA", "MU"])
        self.assertTrue(all(row["source_type"] == "company_release" for row in first))
        self.assertTrue(all(row["provider"] == "official_company_source" for row in first))
        self.assertTrue(all(row["filing_type"] is None for row in first))
        for record in first:
            self.assert_public_record(record)

    def test_sec_live_config_includes_frequent_primary_source_coverage(self) -> None:
        config = json.loads((ROOT / "news/config/sec_companies.json").read_text(encoding="utf-8"))
        forms = {str(value).strip().upper() for value in config["forms"]}
        self.assertIn("4", forms)
        self.assertIn("8-K", forms)
        self.assertIn("10-Q", forms)
        self.assertIn("10-K", forms)

    def test_duplicate_sec_accession_fails_closed(self) -> None:
        payload = load_fixture("sec_filings.json")
        payload = copy.deepcopy(payload)
        payload["filings"].append(copy.deepcopy(payload["filings"][0]))
        with self.assertRaisesRegex(CollectorError, "duplicate SEC accession"):
            collect_sec_fixture(payload, collected_at_utc=COLLECTED_AT)

    def test_duplicate_company_release_id_fails_closed(self) -> None:
        payload = load_fixture("company_releases.json")
        payload = copy.deepcopy(payload)
        payload["releases"].append(copy.deepcopy(payload["releases"][0]))
        with self.assertRaisesRegex(CollectorError, "duplicate company release ID"):
            collect_company_release_fixture(payload, collected_at_utc=COLLECTED_AT)

    def test_live_modes_require_reviewed_config_and_user_agents(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "out.jsonl"
            with self.assertRaisesRegex(CollectorError, "live SEC collection requires --config"):
                sec_main([
                    "--output", str(output),
                    "--collected-at", COLLECTED_AT,
                    "--mode", "live",
                ])
            with self.assertRaisesRegex(CollectorError, "live company collection requires --config"):
                company_main([
                    "--output", str(output),
                    "--collected-at", COLLECTED_AT,
                    "--mode", "live",
                ])
            with self.assertRaisesRegex(CollectorError, "declared user agent"):
                sec_main([
                    "--config", str(ROOT / "news/config/sec_companies.json"),
                    "--output", str(output),
                    "--collected-at", COLLECTED_AT,
                    "--mode", "live",
                ])
            with self.assertRaisesRegex(CollectorError, "requires a user agent"):
                company_main([
                    "--config", str(ROOT / "news/config/official_company_sources.json"),
                    "--output", str(output),
                    "--collected-at", COLLECTED_AT,
                    "--mode", "live",
                ])

    def test_cli_writes_canonical_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temp = Path(temporary)
            sec_output = temp / "sec.jsonl"
            company_output = temp / "company.jsonl"
            self.assertEqual(sec_main([
                "--input", str(FIXTURES / "sec_filings.json"),
                "--output", str(sec_output),
                "--collected-at", COLLECTED_AT,
            ]), 0)
            self.assertEqual(company_main([
                "--input", str(FIXTURES / "company_releases.json"),
                "--output", str(company_output),
                "--collected-at", COLLECTED_AT,
            ]), 0)
            sec_rows = [json.loads(line) for line in sec_output.read_text(encoding="utf-8").splitlines()]
            company_rows = [json.loads(line) for line in company_output.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(len(sec_rows), 2)
            self.assertEqual(len(company_rows), 2)

    def test_schema_is_closed_and_requires_hardening_fields(self) -> None:
        schema = json.loads((ROOT / "news/schemas/news_record.schema.json").read_text(encoding="utf-8"))
        self.assertFalse(schema["additionalProperties"])
        required = set(schema["required"])
        self.assertIn("source_hash", required)
        self.assertIn("synthetic_content_used", required)
        self.assertIn("source_content_modified", required)
        self.assertEqual(schema["properties"]["synthetic_content_used"]["const"], False)
        self.assertEqual(schema["properties"]["source_content_modified"]["const"], False)


if __name__ == "__main__":
    unittest.main()
