from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from ai_market_news.build_preview_artifacts import build_preview_artifacts
from ai_market_news.collect_company_releases import collect_company_release_fixture
from ai_market_news.collect_sec import collect_sec_fixture
from ai_market_news.collector_common import CollectorError, write_jsonl
from ai_market_news.normalize_news import normalize_record
from ai_market_news.transform_news import transform_records


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).resolve().parent / "fixtures"
COLLECTED_AT = "2026-07-10T18:00:00Z"
SOURCE_COMMIT = "a" * 40


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def transformed_records() -> list[dict]:
    sec = collect_sec_fixture(load_fixture("sec_filings.json"), collected_at_utc=COLLECTED_AT)
    company = collect_company_release_fixture(load_fixture("company_releases.json"), collected_at_utc=COLLECTED_AT)
    return transform_records([normalize_record(record) for record in sec + company])


class PublicNewsPreviewTests(unittest.TestCase):
    def test_preview_artifacts_are_complete_and_non_publishing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            news_path = Path(temporary) / "news.jsonl"
            write_jsonl(transformed_records(), news_path)
            receipt, manifest, report = build_preview_artifacts(
                news_path=news_path,
                source_repository="poudlesuman32-star/ai-market-news",
                source_commit=SOURCE_COMMIT,
                run_id="preview-test-1",
                generated_at_utc=COLLECTED_AT,
                collection_mode="fixture",
            )
        self.assertTrue(receipt["collection_complete"])
        self.assertEqual(receipt["record_count"], 4)
        self.assertEqual(receipt["provider_count"], 2)
        self.assertTrue(receipt["private_content_excluded"])
        self.assertEqual(manifest["publication_status"], "preview_only")
        self.assertIsNone(manifest["data_commit"])
        self.assertIsNone(manifest["public_commit"])
        self.assertFalse(report["publication_enabled"])
        self.assertFalse(report["contents_write_permission_authorized"])
        self.assertFalse(report["schedule_enabled"])
        self.assertFalse(report["provider_network_calls_enabled"])
        self.assertFalse(report["secrets_required"])
        self.assertFalse(report["external_writes_enabled"])
        self.assertEqual(report["artifact_retention_days"], 3)
        self.assertEqual(report["required_successful_preview_runs"], 5)

    def test_private_field_contamination_fails_closed(self) -> None:
        records = transformed_records()
        records[0]["private_notes"] = "must not publish"
        with tempfile.TemporaryDirectory() as temporary:
            news_path = Path(temporary) / "news.jsonl"
            write_jsonl(records, news_path)
            with self.assertRaisesRegex(CollectorError, "private fields detected"):
                build_preview_artifacts(
                    news_path=news_path,
                    source_repository="poudlesuman32-star/ai-market-news",
                    source_commit=SOURCE_COMMIT,
                    run_id="preview-test-2",
                    generated_at_utc=COLLECTED_AT,
                    collection_mode="fixture",
                )

    def test_preview_gate_has_five_unique_runs_and_separate_approval(self) -> None:
        gate = json.loads((ROOT / "news/config/public_news_preview_gate.json").read_text(encoding="utf-8"))
        self.assertEqual(gate["required_successful_runs"], 5)
        self.assertEqual(gate["successful_runs_recorded"], 5)
        self.assertEqual(len(gate["successful_runs"]), 5)
        self.assertTrue(gate["gate_satisfied"])
        self.assertTrue(gate["review_approved"])
        self.assertEqual(gate["approved_by"], "poudlesuman32-star")
        self.assertIsNotNone(gate["approved_at_utc"])
        self.assertTrue(gate["publication_authorized"])
        self.assertTrue(gate["contents_write_permission_authorized"])
        self.assertFalse(gate["schedule_authorized"])
        self.assertFalse(gate["secrets_authorized"])
        self.assertFalse(gate["external_writes_authorized"])
        run_keys = {
            (run["workflow_run_id"], run["workflow_run_attempt"])
            for run in gate["successful_runs"]
        }
        artifact_hashes = {
            run["artifact_bundle_sha256"]
            for run in gate["successful_runs"]
        }
        self.assertEqual(len(run_keys), 5)
        self.assertEqual(len(artifact_hashes), 5)
        self.assertTrue(all(run["accepted_event_count"] > 0 for run in gate["successful_runs"]))

    def test_manual_preview_workflow_is_read_only(self) -> None:
        workflow = (ROOT / ".github/workflows/collect-public-news.yml").read_text(encoding="utf-8")
        lowered = workflow.lower()
        self.assertIn("workflow_dispatch:", workflow)
        self.assertNotIn("pull_request:", workflow)
        self.assertNotIn("schedule:", lowered)
        self.assertIn("contents: read", workflow)
        self.assertNotIn("contents: write", workflow)
        self.assertNotIn("secrets.", lowered)
        self.assertNotIn("git push", lowered)
        self.assertNotIn("public-news-data", workflow)
        self.assertIn("retention-days: 3", workflow)
        self.assertIn("news.jsonl", workflow)
        self.assertIn("collection_receipt.json", workflow)
        self.assertIn("news_manifest.preview.json", workflow)
        self.assertIn("run_report.json", workflow)


if __name__ == "__main__":
    unittest.main()
