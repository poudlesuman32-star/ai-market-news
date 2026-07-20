from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from ai_market_news.assess_source_novelty import assess_source_novelty, main
from ai_market_news.collector_common import CollectorError


def record(
    *,
    source_hash: str,
    collected_at: str,
    record_id: str,
    url: str,
    provider: str = "official_company_source",
    ticker: str = "AAPL",
    source_type: str = "company_release",
    filing_type: str | None = None,
    published_at: str = "2026-07-17T12:00:00Z",
) -> dict:
    return {
        "provider": provider,
        "provider_article_id": url,
        "source_url": url,
        "source_hash": source_hash,
        "published_at_utc": published_at,
        "ticker": ticker,
        "source_ticker": ticker,
        "source_type": source_type,
        "filing_type": filing_type,
        "collected_at_utc": collected_at,
        "record_id": record_id,
        "event_id": record_id,
        "duplicate_group_id": record_id,
    }


def write_jsonl(path: Path, records: list[dict]) -> None:
    path.write_text("".join(json.dumps(value, sort_keys=True) + "\n" for value in records), encoding="utf-8")


class SourceNoveltyTests(unittest.TestCase):
    def test_timestamp_and_derived_ids_do_not_create_material_novelty(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            previous = root / "previous.jsonl"
            current = root / "current.jsonl"
            write_jsonl(previous, [record(source_hash="a" * 64, collected_at="2026-07-17T12:01:00Z", record_id="old", url="https://example.com/a")])
            write_jsonl(current, [record(source_hash="a" * 64, collected_at="2026-07-17T13:01:00Z", record_id="new", url="https://example.com/a")])
            result = assess_source_novelty(current_path=current, previous_path=previous)
        self.assertFalse(result["materially_novel"])
        self.assertEqual(result["novelty_disposition"], "duplicate_identity_set")
        self.assertEqual(result["new_record_count"], 0)
        self.assertEqual(result["unchanged_record_count"], 1)
        self.assertEqual(result["source_content_sha256"], result["previous_source_content_sha256"])
        self.assertEqual(result["new_identity_breakdown"], [])
        self.assertEqual(result["current_identity_breakdown"][0]["record_count"], 1)

    def test_new_primary_source_record_qualifies(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            previous = root / "previous.jsonl"
            current = root / "current.jsonl"
            old = record(source_hash="a" * 64, collected_at="2026-07-17T12:01:00Z", record_id="old", url="https://example.com/a")
            new = record(
                source_hash="b" * 64,
                collected_at="2026-07-17T13:01:00Z",
                record_id="new",
                url="https://www.sec.gov/Archives/example-b",
                provider="sec_edgar",
                ticker="MU",
                source_type="sec_filing",
                filing_type="8-K",
                published_at="2026-07-18T12:00:00Z",
            )
            write_jsonl(previous, [old])
            write_jsonl(current, [old, new])
            result = assess_source_novelty(current_path=current, previous_path=previous)
        self.assertTrue(result["materially_novel"])
        self.assertEqual(result["novelty_disposition"], "novel_stable_identities")
        self.assertEqual(result["new_record_count"], 1)
        self.assertEqual(result["unchanged_record_count"], 1)
        self.assertEqual(
            result["new_identity_breakdown"],
            [
                {
                    "provider": "sec_edgar",
                    "ticker": "MU",
                    "source_type": "sec_filing",
                    "filing_type": "8-K",
                    "record_count": 1,
                    "latest_published_at_utc": "2026-07-18T12:00:00Z",
                }
            ],
        )

    def test_removal_only_is_explicit_and_source_specific(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            previous = root / "previous.jsonl"
            current = root / "current.jsonl"
            retained = record(source_hash="a" * 64, collected_at="2026-07-17T12:01:00Z", record_id="old", url="https://example.com/a")
            removed = record(
                source_hash="c" * 64,
                collected_at="2026-07-17T12:01:00Z",
                record_id="removed",
                url="https://www.sec.gov/Archives/example-c",
                provider="sec_edgar",
                ticker="NVDA",
                source_type="sec_filing",
                filing_type="4",
                published_at="2026-06-16T12:00:00Z",
            )
            write_jsonl(previous, [retained, removed])
            write_jsonl(current, [retained])
            result = assess_source_novelty(current_path=current, previous_path=previous)
        self.assertFalse(result["materially_novel"])
        self.assertEqual(result["novelty_disposition"], "removal_only")
        self.assertEqual(result["removed_record_count"], 1)
        self.assertEqual(result["new_identity_breakdown"], [])
        self.assertEqual(result["removed_identity_breakdown"][0]["provider"], "sec_edgar")
        self.assertEqual(result["removed_identity_breakdown"][0]["ticker"], "NVDA")
        self.assertEqual(result["removed_identity_breakdown"][0]["filing_type"], "4")

    def test_new_identities_below_threshold_are_not_eligible(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            previous = root / "previous.jsonl"
            current = root / "current.jsonl"
            old = record(source_hash="a" * 64, collected_at="2026-07-17T12:01:00Z", record_id="old", url="https://example.com/a")
            new = record(source_hash="b" * 64, collected_at="2026-07-17T13:01:00Z", record_id="new", url="https://example.com/b")
            write_jsonl(previous, [old])
            write_jsonl(current, [old, new])
            result = assess_source_novelty(current_path=current, previous_path=previous, minimum_new_records=2)
        self.assertFalse(result["materially_novel"])
        self.assertEqual(result["novelty_disposition"], "insufficient_new_stable_identities")
        self.assertEqual(result["new_record_count"], 1)

    def test_missing_previous_snapshot_is_an_explicit_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            current = Path(directory) / "current.jsonl"
            write_jsonl(current, [record(source_hash="a" * 64, collected_at="2026-07-17T12:01:00Z", record_id="one", url="https://example.com/a")])
            result = assess_source_novelty(current_path=current, previous_path=None)
        self.assertFalse(result["baseline_present"])
        self.assertTrue(result["materially_novel"])
        self.assertEqual(result["novelty_disposition"], "baseline_established")
        self.assertEqual(result["new_record_count"], 1)
        self.assertEqual(result["new_identity_breakdown"], result["current_identity_breakdown"])

    def test_report_only_writes_receipt_for_repeated_period_without_authorization(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            previous = root / "previous.jsonl"
            current = root / "current.jsonl"
            output = root / "period.json"
            value = record(source_hash="a" * 64, collected_at="2026-07-17T12:01:00Z", record_id="one", url="https://example.com/a")
            write_jsonl(previous, [value])
            write_jsonl(current, [{**value, "collected_at_utc": "2026-07-17T13:01:00Z", "record_id": "two"}])
            status = main(
                [
                    "--current",
                    str(current),
                    "--previous",
                    str(previous),
                    "--output",
                    str(output),
                    "--report-only",
                ]
            )
            receipt = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(status, 0)
        self.assertEqual(receipt["schema_version"], "1.1.0")
        self.assertTrue(receipt["report_only"])
        self.assertFalse(receipt["materially_novel"])
        self.assertEqual(receipt["novelty_disposition"], "duplicate_identity_set")
        self.assertIn("current_identity_breakdown", receipt)
        self.assertFalse(receipt["registration_authorized"])
        self.assertFalse(receipt["publication_authorized"])

    def test_standard_cli_still_rejects_repeated_period(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            previous = root / "previous.jsonl"
            current = root / "current.jsonl"
            output = root / "period.json"
            value = record(source_hash="a" * 64, collected_at="2026-07-17T12:01:00Z", record_id="one", url="https://example.com/a")
            write_jsonl(previous, [value])
            write_jsonl(current, [{**value, "collected_at_utc": "2026-07-17T13:01:00Z", "record_id": "two"}])
            with self.assertRaisesRegex(CollectorError, "adds no materially new source records"):
                main(["--current", str(current), "--previous", str(previous), "--output", str(output)])


if __name__ == "__main__":
    unittest.main()
