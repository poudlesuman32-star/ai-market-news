from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts/collect_sec_universe_pilot.py"
CONTRACT_PATH = ROOT / "contracts/PPI-SEC-UNIVERSE-PILOT-001-R1.json"
WORKFLOW_PATH = ROOT / ".github/workflows/ppi-sec-universe-pilot.yml"

spec = importlib.util.spec_from_file_location("sec_pilot", SCRIPT_PATH)
assert spec and spec.loader
sec_pilot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sec_pilot)


def fixture_payload(rows: list[list[object]]) -> bytes:
    return json.dumps(
        {"fields": ["cik", "name", "ticker", "exchange"], "data": rows},
        separators=(",", ":"),
    ).encode("utf-8")


class SecUniversePilotTests(unittest.TestCase):
    def test_contract_is_narrow_public_only_authority(self) -> None:
        value = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        self.assertEqual(value["contract_id"], "PPI-SEC-UNIVERSE-PILOT-001-R1")
        self.assertEqual(value["source"]["url"], sec_pilot.SOURCE_URL)
        self.assertEqual(value["source"]["pilot_max_attempts"], 3)
        self.assertEqual(value["pilot"]["candidate_limit"], 500)
        self.assertTrue(value["authority"]["remote_fetch"])
        self.assertTrue(value["authority"]["sec_bulk_universe_fetch"])
        for key in (
            "provider_credentials",
            "screening",
            "deep_evidence_collection",
            "private_repository_access",
            "private_dispatch",
            "billing_budget_mutation",
            "registry_mutation",
            "production",
            "publication",
            "broker",
            "orders",
            "trading",
            "mmm_raw_data",
            "r12",
        ):
            self.assertFalse(value["authority"][key], key)
        self.assertEqual(value["authorized_actions"], [])

    def test_parser_is_deterministic_and_filters_exchanges(self) -> None:
        rows = []
        exchanges = ["NYSE", "Nasdaq", "NYSE American"]
        for index in range(700):
            rows.append([index + 1, f"Company {index}", f"T{index}", exchanges[index % 3]])
        rows.extend([
            [9999999, "OTC Company", "OTCX", "OTC"],
            [9999998, "No Exchange", "NONE", None],
            [9999997, "Missing Ticker", None, "NYSE"],
        ])
        payload = fixture_payload(rows)
        first, excluded_first, count_first = sec_pilot.parse_source(payload)
        second, excluded_second, count_second = sec_pilot.parse_source(payload)
        self.assertEqual(first, second)
        self.assertEqual(excluded_first, excluded_second)
        self.assertEqual(count_first, count_second)
        self.assertEqual(len(first), 500)
        self.assertEqual(len({row["candidate_id"] for row in first}), 500)
        self.assertEqual(excluded_first["unsupported_exchange"], 2)
        self.assertEqual(excluded_first["missing_ticker"], 1)
        self.assertTrue(all(row["classification_status"] == "unresolved" for row in first))

    def test_parser_rejects_field_drift(self) -> None:
        payload = json.dumps({"fields": ["ticker"], "data": []}).encode("utf-8")
        with self.assertRaises(sec_pilot.PilotError):
            sec_pilot.parse_source(payload)

    def test_same_source_produces_same_snapshot_hash(self) -> None:
        rows = [[index + 1, f"Company {index}", f"X{index}", "NYSE"] for index in range(600)]
        payload = fixture_payload(rows)
        candidates, excluded, source_rows = sec_pilot.parse_source(payload)
        http = {
            "status": 200,
            "content_type": "application/json",
            "content_encoding": None,
            "etag": None,
            "last_modified": None,
            "attempts": 1,
        }
        first = sec_pilot.build_manifest(
            payload=payload,
            http_metadata=http,
            candidates=candidates,
            excluded=excluded,
            source_rows=source_rows,
            generated_at="2026-07-26T00:00:00Z",
        )
        second = sec_pilot.build_manifest(
            payload=payload,
            http_metadata=http,
            candidates=candidates,
            excluded=excluded,
            source_rows=source_rows,
            generated_at="2026-07-27T00:00:00Z",
        )
        self.assertEqual(first["snapshot_sha256"], second["snapshot_sha256"])
        self.assertNotEqual(first["manifest_core_sha256"], second["manifest_core_sha256"])

    def test_missing_user_agent_blocks_without_network(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            sec_pilot.write_blocked(output, "missing")
            blocked = json.loads((output / "blocked.json").read_text(encoding="utf-8"))
            self.assertFalse(blocked["remote_fetch_performed"])
            self.assertFalse(blocked["private_access"])
            self.assertEqual(blocked["status"], "blocked")

    def test_workflow_is_public_only_and_uses_repository_variable(self) -> None:
        text = WORKFLOW_PATH.read_text(encoding="utf-8")
        self.assertIn("cron: '37 6 * * 3'", text)
        self.assertIn("permissions:\n  contents: read", text)
        self.assertIn("vars.PPI_SEC_USER_AGENT", text)
        self.assertIn("--blocked-if-missing-user-agent", text)
        self.assertIn("actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683", text)
        self.assertIn("actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02", text)
        self.assertIn("persist-credentials: false", text)
        for forbidden in (
            "secrets.",
            "musksuman3/ai-signal-engine",
            "PPI_ALPHA_VANTAGE_API_KEY",
            "PPI_MARKETDATA_TOKEN",
            "private_dispatch",
            "registry_mutation",
            "contents: write",
            "pull-requests: write",
            "issues: write",
        ):
            self.assertNotIn(forbidden, text)


if __name__ == "__main__":
    unittest.main()
