from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from ai_market_news.assess_source_novelty import assess_source_novelty


def record(*, source_hash: str, collected_at: str, record_id: str, url: str) -> dict:
    return {
        "provider": "official_company_source",
        "provider_article_id": url,
        "source_url": url,
        "source_hash": source_hash,
        "published_at_utc": "2026-07-17T12:00:00Z",
        "ticker": "AAPL",
        "source_ticker": "AAPL",
        "source_type": "company_release",
        "filing_type": None,
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
        self.assertEqual(result["new_record_count"], 0)
        self.assertEqual(result["unchanged_record_count"], 1)
        self.assertEqual(result["source_content_sha256"], result["previous_source_content_sha256"])

    def test_new_primary_source_record_qualifies(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            previous = root / "previous.jsonl"
            current = root / "current.jsonl"
            old = record(source_hash="a" * 64, collected_at="2026-07-17T12:01:00Z", record_id="old", url="https://example.com/a")
            new = record(source_hash="b" * 64, collected_at="2026-07-17T13:01:00Z", record_id="new", url="https://example.com/b")
            write_jsonl(previous, [old])
            write_jsonl(current, [old, new])
            result = assess_source_novelty(current_path=current, previous_path=previous)
        self.assertTrue(result["materially_novel"])
        self.assertEqual(result["new_record_count"], 1)
        self.assertEqual(result["unchanged_record_count"], 1)

    def test_missing_previous_snapshot_is_an_explicit_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            current = Path(directory) / "current.jsonl"
            write_jsonl(current, [record(source_hash="a" * 64, collected_at="2026-07-17T12:01:00Z", record_id="one", url="https://example.com/a")])
            result = assess_source_novelty(current_path=current, previous_path=None)
        self.assertFalse(result["baseline_present"])
        self.assertTrue(result["materially_novel"])
        self.assertEqual(result["new_record_count"], 1)


if __name__ == "__main__":
    unittest.main()
