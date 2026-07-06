import unittest
from datetime import date
from pathlib import Path

from scripts.contract_common import load_object
from scripts.validate_latest_pointer import validate_latest_pointer
from scripts.validate_market_manifest import validate_market_manifest

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
SNAPSHOT = FIXTURES / "snapshots" / "2026-07-05T234500Z-test"


class ValidMarketArtifactTests(unittest.TestCase):
    def test_valid_manifest_and_pointer(self):
        symbols = load_object(ROOT / "config" / "iteration_16_symbols.json")
        collection = load_object(ROOT / "config" / "iteration_16_collection.json")
        summary = validate_market_manifest(
            SNAPSHOT / "market_artifact_manifest.json",
            market_root=FIXTURES,
            symbols_config=symbols,
            collection_config=collection,
            today=date(2026, 7, 5),
        )
        pointer = validate_latest_pointer(FIXTURES / "latest_valid.json", collection_config=collection)
        self.assertEqual(summary.row_count, 11)
        self.assertFalse(pointer["target_window_complete"])


if __name__ == "__main__":
    unittest.main()
