from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from ai_market_news.build_live_candidate_artifacts import build_live_candidate_artifacts
from ai_market_news.collector_common import CollectorError


SOURCE_COMMIT = "a" * 40


def write_news(path: Path) -> None:
    records = [
        {
            "record_id": "record-sec",
            "event_id": "event-sec",
            "ticker": "AAPL",
            "published_at_utc": "2026-07-11T12:00:00Z",
            "provider": "sec_edgar",
            "validation": "transformed_valid",
            "synthetic_content_used": False,
            "source_content_modified": False,
        },
        {
            "record_id": "record-company",
            "event_id": "event-company",
            "ticker": "NVDA",
            "published_at_utc": "2026-07-11T13:00:00Z",
            "provider": "official_company_source",
            "validation": "transformed_valid",
            "synthetic_content_used": False,
            "source_content_modified": False,
        },
    ]
    path.write_text("".join(json.dumps(record, sort_keys=True) + "\n" for record in records), encoding="utf-8")


class LiveCandidateArtifactBuilderTests(unittest.TestCase):
    def test_schedule_is_recorded_honestly_without_enabling_publication(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            news = Path(temporary) / "news.jsonl"
            write_news(news)
            receipt, manifest, report = build_live_candidate_artifacts(
                news_path=news,
                source_commit=SOURCE_COMMIT,
                run_id="live-candidate-1-1",
                generated_at_utc="2026-07-11T14:00:00Z",
                workflow_event="schedule",
                workflow_run_id="1",
                workflow_run_attempt="1",
                runtime_seconds=2,
                sec_request_count=3,
                company_request_count=2,
                raw_event_count=2,
                normalized_event_count=2,
                duplicate_count=0,
                provider_failures=[],
            )
        self.assertEqual(receipt["workflow_event"], "schedule")
        self.assertTrue(receipt["candidate_only"])
        self.assertTrue(manifest["candidate_only"])
        self.assertEqual(manifest["publication_status"], "preview_only")
        self.assertEqual(report["workflow_event"], "schedule")
        self.assertEqual(report["phase"], "automated_candidate_preview")
        self.assertTrue(report["schedule_enabled"])
        self.assertTrue(report["candidate_only"])
        self.assertFalse(report["publication_enabled"])
        self.assertFalse(report["contents_write_permission_authorized"])
        self.assertFalse(report["external_writes_enabled"])
        self.assertFalse(report["published_to_repository"])
        self.assertIn("independent_validation.json", report["required_artifacts"])

    def test_unsupported_trigger_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            news = Path(temporary) / "news.jsonl"
            write_news(news)
            with self.assertRaisesRegex(CollectorError, "unsupported live candidate workflow event"):
                build_live_candidate_artifacts(
                    news_path=news,
                    source_commit=SOURCE_COMMIT,
                    run_id="live-candidate-1-1",
                    generated_at_utc="2026-07-11T14:00:00Z",
                    workflow_event="push",
                    workflow_run_id="1",
                    workflow_run_attempt="1",
                    runtime_seconds=2,
                    sec_request_count=3,
                    company_request_count=2,
                    raw_event_count=2,
                    normalized_event_count=2,
                    duplicate_count=0,
                    provider_failures=[],
                )


if __name__ == "__main__":
    unittest.main()
