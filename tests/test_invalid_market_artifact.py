import unittest
from datetime import date
from pathlib import Path

from scripts.contract_common import ContractError, load_object
from scripts.validate_market_manifest import validate_market_manifest

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
INVALID = FIXTURES / "invalid"


class InvalidMarketArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.symbols = load_object(ROOT / "config" / "iteration_16_symbols.json")
        cls.collection = load_object(ROOT / "config" / "iteration_16_collection.json")

    def validate(self, name):
        return validate_market_manifest(
            INVALID / name,
            market_root=FIXTURES,
            symbols_config=self.symbols,
            collection_config=self.collection,
            today=date(2026, 7, 5),
        )

    def test_synthetic_manifest_fails(self):
        with self.assertRaisesRegex(ContractError, "synthetic prices"):
            self.validate("synthetic_manifest.json")

    def test_hash_mismatch_fails(self):
        with self.assertRaisesRegex(ContractError, "hash mismatch"):
            self.validate("hash_mismatch_manifest.json")


if __name__ == "__main__":
    unittest.main()
