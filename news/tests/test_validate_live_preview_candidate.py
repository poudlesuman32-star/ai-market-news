from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from ai_market_news.validate_live_preview_candidate import validate_live_preview_candidate


SOURCE_COMMIT = "a" * 40
RUN_ID = "live-preview-100-1"


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, records: list[dict]) -> None:
    path.write_text("".join(json.dumps(record, sort_keys=True) + "\n" for record in records), encoding="utf-8")


def records() -> list[dict]:
    common = {
        "primary_source": True,
        "validation": "transformed_valid",
        "synthetic_content_used": False,
        "source_content_modified": False,
    }
    return [
        {
            **common,
            "record_id": "record-sec",
            "event_id": "event-sec",
            "provider": "sec_edgar",
        },
        {
            **common,
            "record_id": "record-company",
            "event_id": "event-company",
            "provider": "official_company_source",
        },
    ]


def bundle(root: Path, *, workflow_event: str = "schedule") -> tuple[Path, Path, Path, Path]:
    news = root / "news.jsonl"
    receipt_path = root / "collection_receipt.json"
    manifest_path = root / "news_manifest.preview.json"
    report_path = root / "run_report.json"
    values = records()
    write_jsonl(news, values)
    dataset_hash = hashlib.sha256(news.read_bytes()).hexdigest()
    provider_counts = {"official_company_source": 1, "sec_edgar": 1}
    receipt = {
        "run_id": RUN_ID,
        "collection_mode": "live_primary_sources",
        "source_repository": "poudlesuman32-star/ai-market-news",
        "source_commit": SOURCE_COMMIT,
        "record_count": 2,
        "event_count": 2,
        "provider_counts": provider_counts,
        "request_counts": {"sec": 3, "official_company_sources": 2, "polygon": 0, "finnhub": 0},
        "provider_failures": [],
        "dataset_sha256": dataset_hash,
        "synthetic_content_used": False,
        "source_content_modified": False,
        "private_content_excluded": True,
    }
    manifest = {
        "publication_status": "preview_only",
        "snapshot_path": f"snapshots/{RUN_ID}",
        "source_repository": "poudlesuman32-star/ai-market-news",
        "source_commit": SOURCE_COMMIT,
        "data_commit": None,
        "public_commit": None,
        "file_sha256": dataset_hash,
        "record_count": 2,
        "event_count": 2,
        "provider_counts": provider_counts,
        "synthetic_content_used": False,
        "source_content_modified": False,
        "private_content_excluded": True,
    }
    gate_checks = {
        "supported_read_only_trigger": True,
        "sec_network_requests_recorded": True,
        "official_company_network_requests_recorded": True,
        "accepted_sec_record_present": True,
        "accepted_official_company_record_present": True,
        "provider_failures_empty": True,
        "accepted_events_present": True,
        "rejected_events_empty": True,
        "publication_disabled": True,
        "contents_write_disabled": True,
        "external_writes_disabled": True,
    }
    report = {
        "run_id": RUN_ID,
        "workflow_event": workflow_event,
        "source_commit": SOURCE_COMMIT,
        "collection_mode": "live_primary_sources",
        "accepted_event_count": 2,
        "rejected_event_count": 0,
        "provider_failures": [],
        "this_run_qualifies": True,
        "qualification_exclusion_reasons": [],
        "live_primary_countability_checks": gate_checks,
        "publication_enabled": False,
        "published_to_repository": False,
        "contents_write_permission_authorized": False,
        "external_writes_enabled": False,
        "secrets_required": False,
        "schedule_enabled": workflow_event == "schedule",
    }
    write_json(receipt_path, receipt)
    write_json(manifest_path, manifest)
    write_json(report_path, report)
    return news, receipt_path, manifest_path, report_path


class IndependentLivePreviewValidationTests(unittest.TestCase):
    def validate(self, root: Path, *, workflow_event: str = "schedule") -> dict:
        news, receipt, manifest, report = bundle(root, workflow_event=workflow_event)
        return validate_live_preview_candidate(
            news_path=news,
            receipt_path=receipt,
            manifest_path=manifest,
            report_path=report,
        )

    def test_scheduled_mixed_provider_candidate_is_valid(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            result = self.validate(Path(temporary))
        self.assertTrue(result["candidate_valid"])
        self.assertEqual(result["failures"], [])
        self.assertFalse(result["publication_authorized"])
        self.assertFalse(result["official_r9_count_authorized"])

    def test_manual_candidate_is_also_valid(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            result = self.validate(Path(temporary), workflow_event="workflow_dispatch")
        self.assertTrue(result["candidate_valid"])

    def test_dataset_tampering_fails_hash_and_count_validation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            news, receipt, manifest, report = bundle(root)
            with news.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps({**records()[0], "record_id": "tampered", "event_id": "tampered"}) + "\n")
            result = validate_live_preview_candidate(
                news_path=news,
                receipt_path=receipt,
                manifest_path=manifest,
                report_path=report,
            )
        self.assertFalse(result["candidate_valid"])
        self.assertIn("dataset_hash_consistent", result["failures"])
        self.assertIn("record_count_consistent", result["failures"])

    def test_provider_count_mismatch_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            news, receipt, manifest, report = bundle(root)
            receipt_value = json.loads(receipt.read_text(encoding="utf-8"))
            receipt_value["provider_counts"] = {"official_company_source": 2}
            write_json(receipt, receipt_value)
            result = validate_live_preview_candidate(
                news_path=news,
                receipt_path=receipt,
                manifest_path=manifest,
                report_path=report,
            )
        self.assertFalse(result["candidate_valid"])
        self.assertIn("provider_counts_consistent", result["failures"])

    def test_publication_permission_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            news, receipt, manifest, report = bundle(root)
            report_value = json.loads(report.read_text(encoding="utf-8"))
            report_value["publication_enabled"] = True
            write_json(report, report_value)
            result = validate_live_preview_candidate(
                news_path=news,
                receipt_path=receipt,
                manifest_path=manifest,
                report_path=report,
            )
        self.assertFalse(result["candidate_valid"])
        self.assertIn("publication_disabled", result["failures"])


if __name__ == "__main__":
    unittest.main()
