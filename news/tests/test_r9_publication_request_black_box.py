from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class R9PublicationRequestBlackBoxTests(unittest.TestCase):
    def write_fixture(self, root: Path) -> dict[str, Path | str]:
        head_sha = "a" * 40
        news = root / "news.jsonl"
        news.write_text('{"record_id":"record-1"}\n', encoding="utf-8")
        digest = hashlib.sha256(news.read_bytes()).hexdigest()
        source_run = {
            "id": 12345,
            "run_attempt": 1,
            "event": "workflow_dispatch",
            "status": "completed",
            "conclusion": "success",
            "head_branch": "main",
            "head_repository": {"full_name": "poudlesuman32-star/ai-market-news"},
            "name": "PPI public news live primary-source preview",
            "head_sha": head_sha,
            "updated_at": "2026-07-13T10:05:00Z",
        }
        receipt = {
            "schema_version": "1.1.0",
            "run_id": "live-preview-12345-1",
            "collection_mode": "live_primary_sources",
            "source_repository": "poudlesuman32-star/ai-market-news",
            "source_commit": head_sha,
            "collection_complete": True,
            "dataset_sha256": digest,
            "provider_counts": {"sec_edgar": 1, "official_company_source": 2},
            "provider_failures": [],
            "synthetic_content_used": False,
            "source_content_modified": False,
            "private_content_excluded": True,
        }
        manifest = {
            "schema_version": "1.1.0",
            "publication_status": "preview_only",
            "source_repository": "poudlesuman32-star/ai-market-news",
            "source_commit": head_sha,
            "file_sha256": digest,
            "synthetic_content_used": False,
            "source_content_modified": False,
            "private_content_excluded": True,
        }
        report = {
            "schema_version": "1.1.0",
            "run_id": "live-preview-12345-1",
            "workflow_run_id": "12345",
            "workflow_run_attempt": "1",
            "workflow_event": "workflow_dispatch",
            "source_commit": head_sha,
            "this_run_qualifies": True,
            "qualification_exclusion_reasons": [],
            "provider_failures": [],
            "schedule_enabled": False,
            "published_to_repository": False,
            "external_writes_enabled": False,
            "contents_write_permission_authorized": False,
        }
        paths: dict[str, Path | str] = {
            "news": news,
            "source_run": root / "source-run.json",
            "receipt": root / "collection_receipt.json",
            "manifest": root / "news_manifest.preview.json",
            "report": root / "run_report.json",
            "output": root / "authorization-request.json",
            "digest": digest,
        }
        for key, value in (
            ("source_run", source_run),
            ("receipt", receipt),
            ("manifest", manifest),
            ("report", report),
        ):
            Path(paths[key]).write_text(json.dumps(value), encoding="utf-8")
        return paths

    def run_cli(self, paths: dict[str, Path | str], *, candidate_sha256: str | None = None) -> subprocess.CompletedProcess[str]:
        command = [
            sys.executable,
            "-m",
            "ai_market_news.validate_r9_publication_request",
            "--source-run",
            str(paths["source_run"]),
            "--news",
            str(paths["news"]),
            "--receipt",
            str(paths["receipt"]),
            "--manifest",
            str(paths["manifest"]),
            "--report",
            str(paths["report"]),
            "--source-run-id",
            "12345",
            "--source-run-attempt",
            "1",
            "--candidate-sha256",
            candidate_sha256 or str(paths["digest"]),
            "--contract-sha256",
            "b" * 64,
            "--authorization-issued-at-utc",
            "2026-07-13T10:10:00Z",
            "--authorization-expires-at-utc",
            "2026-07-14T10:00:00Z",
            "--requested-by",
            "poudlesuman32-star",
            "--now-utc",
            "2026-07-13T10:15:00Z",
            "--output",
            str(paths["output"]),
        ]
        return subprocess.run(command, text=True, capture_output=True, check=False, env=dict(os.environ))

    def test_valid_request_emits_sanitized_request_not_approval_claim(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            paths = self.write_fixture(Path(directory))
            result = self.run_cli(paths)
            self.assertEqual(result.returncode, 0, result.stderr)
            evidence = json.loads(Path(paths["output"]).read_text(encoding="utf-8"))
            self.assertEqual(evidence["validation_result"], "passed")
            self.assertEqual(evidence["source_head_sha"], "a" * 40)
            self.assertEqual(evidence["candidate_sha256"], paths["digest"])
            self.assertEqual(evidence["contract_sha256"], "b" * 64)
            self.assertEqual(evidence["environment"], "ppi-r9-manual-approval")
            self.assertFalse(evidence["environment_gate_passed"])
            self.assertEqual(len(evidence["authorization_request_sha256"]), 64)
            serialized = json.dumps(evidence, sort_keys=True).lower()
            self.assertNotIn("authorization_reason", serialized)
            self.assertNotIn("authorized_by", serialized)
            self.assertNotIn("private", serialized)
            self.assertNotIn("secret", serialized)

    def test_scheduled_source_run_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            paths = self.write_fixture(Path(directory))
            source_run = json.loads(Path(paths["source_run"]).read_text(encoding="utf-8"))
            source_run["event"] = "schedule"
            Path(paths["source_run"]).write_text(json.dumps(source_run), encoding="utf-8")
            result = self.run_cli(paths)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(Path(paths["output"]).exists())

    def test_mismatched_source_commit_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            paths = self.write_fixture(Path(directory))
            report = json.loads(Path(paths["report"]).read_text(encoding="utf-8"))
            report["source_commit"] = "c" * 40
            Path(paths["report"]).write_text(json.dumps(report), encoding="utf-8")
            result = self.run_cli(paths)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(Path(paths["output"]).exists())

    def test_candidate_digest_mismatch_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            paths = self.write_fixture(Path(directory))
            result = self.run_cli(paths, candidate_sha256="d" * 64)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(Path(paths["output"]).exists())

    def test_stale_source_authorization_window_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            paths = self.write_fixture(Path(directory))
            source_run = json.loads(Path(paths["source_run"]).read_text(encoding="utf-8"))
            source_run["updated_at"] = "2026-07-12T09:00:00Z"
            Path(paths["source_run"]).write_text(json.dumps(source_run), encoding="utf-8")
            result = self.run_cli(paths)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(Path(paths["output"]).exists())


if __name__ == "__main__":
    unittest.main()
