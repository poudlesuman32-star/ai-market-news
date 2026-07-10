from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from ai_market_news.collect_company_releases import main as company_main
from ai_market_news.collect_sec import main as sec_main
from ai_market_news.collector_common import CollectorError, build_public_record
from ai_market_news.normalize_news import canonicalize_url, normalize_record
from ai_market_news.transform_news import main as transform_main, transform_records


FIXTURES = Path(__file__).resolve().parent / "fixtures"
COLLECTED_AT = "2026-07-10T18:00:00Z"


def make_record(
    *,
    provider: str,
    article_id: str,
    headline: str,
    summary: str,
    published_at: str,
    source_url: str,
    primary_source: bool,
) -> dict:
    return build_public_record(
        ticker="NVDA",
        published_at_utc=published_at,
        collected_at_utc=COLLECTED_AT,
        source_type="company_release" if primary_source else "commercial_news",
        source_name="NVIDIA Investor Relations" if primary_source else "Example News Provider",
        source_url=source_url,
        headline=headline,
        summary=summary,
        provider=provider,
        provider_article_id=article_id,
        source_ticker="NVDA",
        filing_type=None,
        event_identity=article_id,
        primary_source=primary_source,
    )


class PublicNewsTransformationTests(unittest.TestCase):
    def duplicate_fixture(self) -> list[dict]:
        headline = "NVIDIA announces GPU capacity expansion for data center demand"
        primary = make_record(
            provider="official_company_source",
            article_id="nvda-capacity-20260710",
            headline=headline,
            summary="NVIDIA announced new GPU capacity for data center customers.",
            published_at="2026-07-10T12:00:00Z",
            source_url="https://investor.nvidia.com/news/capacity?utm_source=email",
            primary_source=True,
        )
        commercial = make_record(
            provider="example_news",
            article_id="provider-8842",
            headline=headline,
            summary="A provider reported NVIDIA's GPU capacity expansion for data center demand.",
            published_at="2026-07-10T14:00:00Z",
            source_url="https://news.example.com/nvidia-capacity?gclid=tracking",
            primary_source=False,
        )
        distinct = make_record(
            provider="official_company_source",
            article_id="nvda-networking-20260710",
            headline="NVIDIA launches a new networking platform",
            summary="NVIDIA introduced an Ethernet networking platform for AI infrastructure.",
            published_at="2026-07-10T14:30:00Z",
            source_url="https://investor.nvidia.com/news/networking",
            primary_source=True,
        )
        return [primary, commercial, distinct]

    def test_transform_is_order_independent_and_byte_stable(self) -> None:
        records = self.duplicate_fixture()
        forward = transform_records([normalize_record(record) for record in records])
        reverse = transform_records([normalize_record(record) for record in reversed(records)])
        self.assertEqual(forward, reverse)
        forward_bytes = "".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in forward)
        reverse_bytes = "".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in reverse)
        self.assertEqual(forward_bytes, reverse_bytes)

    def test_cross_provider_duplicate_groups_but_distinct_event_remains_separate(self) -> None:
        transformed = transform_records([normalize_record(record) for record in self.duplicate_fixture()])
        capacity = [row for row in transformed if "capacity expansion" in row["headline"].lower()]
        networking = [row for row in transformed if "networking platform" in row["headline"].lower()]
        self.assertEqual(len(capacity), 2)
        self.assertEqual(len({row["event_id"] for row in capacity}), 1)
        self.assertEqual(len(networking), 1)
        self.assertNotEqual(capacity[0]["event_id"], networking[0]["event_id"])

    def test_deterministic_catalyst_and_infrastructure_tags(self) -> None:
        transformed = transform_records([normalize_record(record) for record in self.duplicate_fixture()])
        capacity = next(row for row in transformed if row["provider"] == "official_company_source" and "capacity expansion" in row["headline"].lower())
        self.assertIn("capacity", capacity["catalyst_tags"])
        self.assertIn("semiconductors", capacity["ai_infrastructure_layers"])
        self.assertIn("compute", capacity["ai_infrastructure_layers"])
        self.assertIn("data_centers", capacity["ai_infrastructure_layers"])
        self.assertEqual(capacity["validation"], "transformed_valid")

    def test_tracking_parameters_are_removed_from_canonical_url(self) -> None:
        self.assertEqual(
            canonicalize_url("https://Example.com/path?utm_source=x&b=2&a=1#section"),
            "https://example.com/path?a=1&b=2",
        )

    def test_duplicate_record_id_fails_closed(self) -> None:
        record = normalize_record(self.duplicate_fixture()[0])
        with self.assertRaisesRegex(CollectorError, "duplicate record_id"):
            transform_records([record, copy.deepcopy(record)])

    def test_synthetic_or_modified_content_fails_closed(self) -> None:
        synthetic = self.duplicate_fixture()[0]
        synthetic["synthetic_content_used"] = True
        with self.assertRaisesRegex(CollectorError, "synthetic content"):
            normalize_record(synthetic)
        modified = self.duplicate_fixture()[0]
        modified["source_content_modified"] = True
        with self.assertRaisesRegex(CollectorError, "modified source content"):
            normalize_record(modified)

    def test_cli_combines_primary_source_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temp = Path(temporary)
            sec_output = temp / "sec.jsonl"
            company_output = temp / "company.jsonl"
            transformed_output = temp / "news.jsonl"
            sec_main([
                "--input", str(FIXTURES / "sec_filings.json"),
                "--output", str(sec_output),
                "--collected-at", COLLECTED_AT,
            ])
            company_main([
                "--input", str(FIXTURES / "company_releases.json"),
                "--output", str(company_output),
                "--collected-at", COLLECTED_AT,
            ])
            self.assertEqual(transform_main([
                "--input", str(sec_output),
                "--input", str(company_output),
                "--output", str(transformed_output),
            ]), 0)
            rows = [json.loads(line) for line in transformed_output.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(len(rows), 4)
            self.assertTrue(all(row["validation"] == "transformed_valid" for row in rows))
            self.assertTrue(all(row["synthetic_content_used"] is False for row in rows))
            self.assertTrue(all(row["source_content_modified"] is False for row in rows))


if __name__ == "__main__":
    unittest.main()
