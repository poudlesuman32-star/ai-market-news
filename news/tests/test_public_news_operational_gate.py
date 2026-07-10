from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from ai_market_news.build_news_latest_pointer import build_latest_pointer
from ai_market_news.build_news_manifest import build_news_manifest
from ai_market_news.build_preview_artifacts import build_preview_artifacts
from ai_market_news.collect_company_releases import collect_company_release_fixture
from ai_market_news.collect_sec import collect_sec_fixture
from ai_market_news.collector_common import CollectorError, write_jsonl
from ai_market_news.normalize_news import normalize_record
from ai_market_news.preview_gate import (
    approve_gate,
    artifact_bundle_sha256,
    record_preview_run,
    require_publication_authorized,
    validate_gate,
)
from ai_market_news.transform_news import transform_records
from ai_market_news.verify_news_publication_transaction import verify_transaction

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).resolve().parent / "fixtures"
COLLECTED_AT = "2026-07-10T18:00:00Z"
SOURCE_COMMIT = "a" * 40


def fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def transformed_records() -> list[dict]:
    sec = collect_sec_fixture(fixture("sec_filings.json"), collected_at_utc=COLLECTED_AT)
    company = collect_company_release_fixture(fixture("company_releases.json"), collected_at_utc=COLLECTED_AT)
    return transform_records([normalize_record(record) for record in sec + company])


def initial_gate() -> dict:
    return json.loads((ROOT / "news/config/public_news_preview_gate.json").read_text(encoding="utf-8"))


def write_preview_bundle(root: Path, *, run_number: int) -> dict:
    news = root / "news.jsonl"
    write_jsonl(transformed_records(), news)
    receipt, manifest, report = build_preview_artifacts(
        news_path=news,
        source_repository="poudlesuman32-star/ai-market-news",
        source_commit=SOURCE_COMMIT,
        run_id=f"preview-test-{run_number}",
        generated_at_utc=COLLECTED_AT,
        collection_mode="fixture",
        workflow_event="workflow_dispatch",
        workflow_run_id=str(1000 + run_number),
        workflow_run_attempt="1",
        runtime_seconds=5,
        raw_event_count=4,
        normalized_event_count=4,
    )
    (root / "collection_receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (root / "news_manifest.preview.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (root / "run_report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def git(root: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True).stdout.strip()


class PublicNewsOperationalGateTests(unittest.TestCase):
    def test_current_gate_is_valid_and_blocks_publication(self) -> None:
        gate = initial_gate()
        validate_gate(gate)
        self.assertFalse(gate["gate_satisfied"])
        self.assertFalse(gate["review_approved"])
        with self.assertRaisesRegex(CollectorError, "publication is not authorized"):
            require_publication_authorized(gate)

    def test_five_unique_runs_require_separate_review_approval(self) -> None:
        gate = initial_gate()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for run_number in range(1, 6):
                run_root = root / str(run_number)
                run_root.mkdir()
                report = write_preview_bundle(run_root, run_number=run_number)
                gate = record_preview_run(
                    gate=gate,
                    report=report,
                    artifact_bundle_hash=artifact_bundle_sha256(run_root),
                    recorded_at_utc=f"2026-07-10T18:00:0{run_number}Z",
                )
        self.assertEqual(gate["successful_runs_recorded"], 5)
        self.assertTrue(gate["gate_satisfied"])
        self.assertFalse(gate["publication_authorized"])
        with self.assertRaisesRegex(CollectorError, "publication is not authorized"):
            require_publication_authorized(gate)

        approved = approve_gate(gate=gate, approver="release-reviewer", approved_at_utc="2026-07-10T19:00:00Z")
        self.assertTrue(approved["review_approved"])
        self.assertTrue(approved["publication_authorized"])
        self.assertTrue(approved["contents_write_permission_authorized"])
        require_publication_authorized(approved)

    def test_duplicate_run_or_artifact_bundle_cannot_count_twice(self) -> None:
        gate = initial_gate()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            report = write_preview_bundle(root, run_number=1)
            bundle_hash = artifact_bundle_sha256(root)
            gate = record_preview_run(
                gate=gate,
                report=report,
                artifact_bundle_hash=bundle_hash,
                recorded_at_utc="2026-07-10T18:00:01Z",
            )
            with self.assertRaisesRegex(CollectorError, "already recorded"):
                record_preview_run(
                    gate=gate,
                    report=report,
                    artifact_bundle_hash=bundle_hash,
                    recorded_at_utc="2026-07-10T18:00:02Z",
                )

    def test_manifest_and_pointer_bind_exact_commits(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            report = write_preview_bundle(root, run_number=1)
            del report
            data_commit = "b" * 40
            manifest = build_news_manifest(
                news_path=root / "news.jsonl",
                receipt_path=root / "collection_receipt.json",
                snapshot_path="snapshots/test-run",
                data_commit=data_commit,
                source_repository="poudlesuman32-star/ai-market-news",
            )
            self.assertEqual(manifest["data_commit"], data_commit)
            self.assertEqual(manifest["record_count"], 4)
            self.assertFalse(manifest["synthetic_content_used"])
            pointer = build_latest_pointer(manifest=manifest, public_commit="c" * 40)
            self.assertEqual(pointer["data_commit"], data_commit)
            self.assertEqual(pointer["public_commit"], "c" * 40)
            self.assertTrue(pointer["collection_complete"])

    def test_transaction_verifier_accepts_only_data_manifest_pointer_sequence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            git(root, "init")
            git(root, "config", "user.name", "test")
            git(root, "config", "user.email", "test@example.com")
            (root / "README.md").write_text("base\n", encoding="utf-8")
            git(root, "add", "README.md")
            git(root, "commit", "-m", "base")
            previous = git(root, "rev-parse", "HEAD")

            snapshot = Path("snapshots/test-run")
            absolute_snapshot = root / snapshot
            absolute_snapshot.mkdir(parents=True)
            write_jsonl(transformed_records(), absolute_snapshot / "news.jsonl")
            receipt, _, _ = build_preview_artifacts(
                news_path=absolute_snapshot / "news.jsonl",
                source_repository="poudlesuman32-star/ai-market-news",
                source_commit=SOURCE_COMMIT,
                run_id="test-run",
                generated_at_utc=COLLECTED_AT,
                collection_mode="fixture",
            )
            (absolute_snapshot / "collection_receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            git(root, "add", str(snapshot / "news.jsonl"), str(snapshot / "collection_receipt.json"))
            git(root, "commit", "-m", "data")
            data_commit = git(root, "rev-parse", "HEAD")

            manifest = build_news_manifest(
                news_path=absolute_snapshot / "news.jsonl",
                receipt_path=absolute_snapshot / "collection_receipt.json",
                snapshot_path=str(snapshot),
                data_commit=data_commit,
                source_repository="poudlesuman32-star/ai-market-news",
            )
            (absolute_snapshot / "news_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            git(root, "add", str(snapshot / "news_manifest.json"))
            git(root, "commit", "-m", "manifest")
            public_commit = git(root, "rev-parse", "HEAD")

            pointer = build_latest_pointer(manifest=manifest, public_commit=public_commit)
            (root / "latest.json").write_text(json.dumps(pointer, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            git(root, "add", "latest.json")
            git(root, "commit", "-m", "pointer")
            pointer_commit = git(root, "rev-parse", "HEAD")

            report = verify_transaction(
                repository_root=root,
                previous_head=previous,
                data_commit=data_commit,
                public_commit=public_commit,
                pointer_commit=pointer_commit,
                snapshot_path=str(snapshot),
            )
            self.assertTrue(report["valid"])

    def test_modified_or_synthetic_public_content_fails_before_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            records = transformed_records()
            records[0]["synthetic_content_used"] = True
            write_jsonl(records, root / "news.jsonl")
            receipt = {
                "collection_complete": True,
                "dataset_sha256": hashlib.sha256((root / "news.jsonl").read_bytes()).hexdigest(),
                "record_count": len(records),
                "synthetic_content_used": False,
                "source_content_modified": False,
                "private_content_excluded": True,
            }
            (root / "collection_receipt.json").write_text(json.dumps(receipt), encoding="utf-8")
            with self.assertRaisesRegex(CollectorError, "synthetic content is forbidden"):
                build_news_manifest(
                    news_path=root / "news.jsonl",
                    receipt_path=root / "collection_receipt.json",
                    snapshot_path="snapshots/test",
                    data_commit="d" * 40,
                    source_repository="poudlesuman32-star/ai-market-news",
                )

    def test_publisher_is_gate_bound_single_push_and_news_branch_only(self) -> None:
        publisher = (ROOT / "scripts/publish_public_news_snapshot.sh").read_text(encoding="utf-8")
        self.assertIn("require-publication", publisher)
        self.assertIn("public-news-data", publisher)
        self.assertNotIn("iteration-16-market-data", publisher)
        self.assertEqual(publisher.count("git -C \"$PUBLISH_ROOT\" push"), 1)
        self.assertIn("Any failure above leaves the remote pointer unchanged", publisher)


if __name__ == "__main__":
    unittest.main()
