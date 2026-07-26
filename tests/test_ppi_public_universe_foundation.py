from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/ppi-public-universe-foundation.yml"
INVENTORY = ROOT / "config/ppi_public_source_inventory.json"
CONTRACT = ROOT / "contracts/PPI-UNIVERSE-US-COMMON-001-R1.json"
SCHEMA = ROOT / "schemas/ppi_public_universe_foundation.schema.json"
VALIDATOR = ROOT / "scripts/validate_ppi_public_universe_foundation.py"

EXPECTED_TICKERS = [
    "AAPL", "MU", "NVDA", "AMD", "AVGO", "INTC",
    "TSM", "ARM", "QCOM", "MRVL", "GFS", "TXN",
]


class PpiPublicUniverseFoundationTests(unittest.TestCase):
    def test_workflow_is_public_read_only_and_no_network(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", text)
        self.assertIn("cron: '17 6 * * 1'", text)
        self.assertIn("permissions:\n  contents: read", text)
        self.assertIn("timeout-minutes: 10", text)
        self.assertIn("persist-credentials: false", text)
        self.assertIn("actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683", text)
        self.assertIn("actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02", text)
        for forbidden in (
            "secrets.",
            "curl ",
            "wget ",
            "requests.",
            "urlopen",
            "workflow_run:",
            "repository_dispatch:",
            "ai-signal-engine",
            "contents: write",
            "actions: write",
            "pull-requests: write",
            "issues: write",
        ):
            self.assertNotIn(forbidden, text)

    def test_inventory_has_free_public_sources_and_screening_hold(self) -> None:
        value = json.loads(INVENTORY.read_text(encoding="utf-8"))
        self.assertFalse(value["private_source_dependency"])
        approved = [item for item in value["sources"] if item["approved"]]
        self.assertTrue(any("listing_universe" in item["operations"] for item in approved))
        self.assertTrue(any("security_identifier_mapping" in item["operations"] for item in approved))
        self.assertFalse(any("lightweight_screening" in item["operations"] for item in approved))
        for item in approved:
            self.assertEqual(item["cost_class"], "free")
            self.assertTrue(item["public_runner_allowed"])
            self.assertFalse(item["requires_private_secret"])
        self.assertEqual(value["authorized_actions"], [])
        self.assertTrue(all(flag is False for flag in value["authority"].values()))

    def test_contract_freezes_batch3_and_minimizes_private_role(self) -> None:
        value = json.loads(CONTRACT.read_text(encoding="utf-8"))
        self.assertEqual(value["contract_id"], "PPI-UNIVERSE-US-COMMON-001-R1")
        self.assertEqual(value["frozen_batch3"]["tickers"], EXPECTED_TICKERS)
        self.assertEqual(value["frozen_batch3"]["bundle_count"], 48)
        self.assertEqual(value["frozen_batch3"]["path_count"], 50)
        self.assertEqual(len(value["frozen_batch3"]["pinned_files"]), 3)
        self.assertEqual(value["universe_scope"]["included_asset_types"], ["common_stock"])
        self.assertEqual(value["universe_scope"]["separately_contracted_asset_types"], ["adr"])
        self.assertEqual(value["identity_layers"]["primary"], "instrument_id")
        self.assertEqual(value["identity_layers"]["security_level_external"], "figi")
        self.assertEqual(value["identity_layers"]["issuer_level_external"], "cik")
        self.assertIn("final_semantic_curation", value["private_minimum_task"])
        self.assertIn("private_calculations", value["private_minimum_task"])
        self.assertIn("final_report", value["private_minimum_task"])
        self.assertEqual(value["authorized_actions"], [])
        self.assertTrue(all(flag is False for flag in value["authority"].values()))

    def test_schema_contains_lifecycle_applicability_event_and_snapshot(self) -> None:
        value = json.loads(SCHEMA.read_text(encoding="utf-8"))
        definitions = value["$defs"]
        self.assertIn("insufficient_history", definitions["applicability_state"]["enum"])
        self.assertIn("invalid_payload", definitions["applicability_state"]["enum"])
        self.assertIn("private_pending", definitions["lifecycle_state"]["enum"])
        self.assertIn("instrument", definitions)
        self.assertIn("universe_event", definitions)
        self.assertIn("snapshot_manifest", definitions)
        required = definitions["instrument"]["required"]
        for field in ("instrument_id", "current_symbol", "cik", "figi", "symbol_history"):
            self.assertIn(field, required)

    def test_validator_has_no_provider_or_private_execution_path(self) -> None:
        text = VALIDATOR.read_text(encoding="utf-8")
        for forbidden in (
            "import requests",
            "urllib",
            "api.github.com",
            "alphavantage",
            "marketdata.app",
            "yfinance",
            "PPI_ALPHA_VANTAGE_API_KEY",
            "PPI_MARKETDATA_TOKEN",
            "/dispatches",
            "registry_pr",
        ):
            self.assertNotIn(forbidden, text)

    def test_validator_builds_safe_readiness_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            completed = subprocess.run(
                [sys.executable, str(VALIDATOR), "--output-root", tmp],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)
            report = json.loads(Path(tmp, "readiness.json").read_text(encoding="utf-8"))
            self.assertEqual(report["status"], "foundation_ready")
            self.assertEqual(report["contract_id"], "PPI-UNIVERSE-US-COMMON-001-R1")
            self.assertEqual(report["inventory"]["approved_screening_source_count"], 0)
            self.assertEqual(len(report["frozen_batch3_git_blobs"]), 3)
            self.assertTrue(all(flag is False for flag in report["authority"].values()))
            summary = Path(tmp, "readiness.md").read_text(encoding="utf-8")
            self.assertIn("Remote fetch performed: `False`", summary)
            self.assertIn("Private repository accessed: `False`", summary)


if __name__ == "__main__":
    unittest.main()
