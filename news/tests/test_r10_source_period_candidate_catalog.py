from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from news.scripts.catalog_r10_source_period_candidates import (
    IDENTITY_FIELDS,
    build_candidate_chain,
    identity_keys,
    source_fingerprint,
)


def record(label: str, *, ticker: str = "AAPL") -> dict[str, object]:
    return {
        "provider": "official_company_source",
        "provider_article_id": label,
        "source_url": f"https://example.com/{label}",
        "source_hash": hashlib.sha256(label.encode()).hexdigest(),
        "published_at_utc": "2026-07-19T00:00:00Z",
        "ticker": ticker,
        "source_ticker": ticker,
        "source_type": "press_release",
        "filing_type": None,
    }


def manifest_entry(root: Path, index: int, records: list[dict[str, object]]) -> dict[str, object]:
    path = root / f"run-{index}.jsonl"
    path.write_text("".join(json.dumps(value, sort_keys=True) + "\n" for value in records), encoding="utf-8")
    return {
        "run_id": 1000 + index,
        "run_attempt": 1,
        "created_at": f"2026-07-{19 + index:02d}T00:00:00Z",
        "head_sha": f"{index:040x}",
        "artifact_name": f"ppi-primary-source-coverage-{1000 + index}-1",
        "artifact_sha256": hashlib.sha256(f"artifact-{index}".encode()).hexdigest(),
        "records_path": str(path),
    }


class R10SourcePeriodCandidateCatalogTests(unittest.TestCase):
    def test_catalog_skips_removal_only_run_and_builds_two_novel_periods(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            baseline = [record("a"), record("b")]
            runs = [
                manifest_entry(root, 1, [record("a")]),
                manifest_entry(root, 2, [record("a"), record("b"), record("c")]),
                manifest_entry(root, 3, [record("a"), record("b"), record("c")]),
                manifest_entry(root, 4, [record("a"), record("b"), record("c"), record("d")]),
            ]
            result = build_candidate_chain(baseline_records=baseline, runs=runs)
            self.assertEqual(result["status"], "candidate_chain_complete")
            self.assertEqual(result["candidate_count"], 2)
            self.assertEqual([value["run_id"] for value in result["candidates"]], [1002, 1004])
            self.assertEqual([value["sequence"] for value in result["candidates"]], [4, 5])
            self.assertEqual(result["diagnostics"][0]["new_primary_record_count"], 0)
            self.assertFalse(result["diagnostics"][0]["eligible"])
            self.assertTrue(all(value["publication_authorized"] is False for value in result["candidates"]))

    def test_fingerprint_matches_frozen_identity_fields(self) -> None:
        values = [record("x"), record("y", ticker="MU")]
        keys = identity_keys(values)
        expected_keys = {
            json.dumps(
                {field: value.get(field) for field in IDENTITY_FIELDS},
                sort_keys=True,
                separators=(",", ":"),
            )
            for value in values
        }
        self.assertEqual(keys, expected_keys)
        self.assertEqual(
            source_fingerprint(keys),
            hashlib.sha256(("\n".join(sorted(expected_keys)) + "\n").encode()).hexdigest(),
        )

    def test_catalog_reports_insufficient_periods_without_fabrication(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            baseline = [record("a"), record("b")]
            result = build_candidate_chain(
                baseline_records=baseline,
                runs=[manifest_entry(root, 1, [record("a")])],
            )
            self.assertEqual(result["status"], "insufficient_novel_periods")
            self.assertEqual(result["candidate_count"], 0)
            self.assertEqual(result["candidates"], [])


if __name__ == "__main__":
    unittest.main()
