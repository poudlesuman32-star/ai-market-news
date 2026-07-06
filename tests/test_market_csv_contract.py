from __future__ import annotations

import csv
import tempfile
import unittest
from datetime import date
from pathlib import Path

from scripts.contract_common import ContractError, load_object
from scripts.validate_market_csv import validate_market_csv

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
VALID_CSV = FIXTURES / "snapshots" / "2026-07-05T234500Z-test" / "market_prices.csv"
TODAY = date(2026, 7, 5)


class MarketCsvContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.symbols = load_object(ROOT / "config" / "iteration_16_symbols.json")
        cls.collection = load_object(ROOT / "config" / "iteration_16_collection.json")

    def validate(self, path: Path):
        return validate_market_csv(
            path,
            symbols_config=self.symbols,
            collection_config=self.collection,
            today=TODAY,
        )

    def test_schema_documents_are_deterministic_json_objects(self) -> None:
        for name in (
            "market_price.schema.json",
            "market_manifest.schema.json",
            "latest_pointer.schema.json",
        ):
            value = load_object(ROOT / "schemas" / name)
            self.assertEqual(value["$schema"], "https://json-schema.org/draft/2020-12/schema")
            self.assertFalse(value["additionalProperties"])

    def test_valid_fixture_passes(self) -> None:
        summary = self.validate(VALID_CSV)
        self.assertEqual(summary.row_count, 11)
        self.assertEqual(summary.symbol_count, 11)

    def test_unknown_symbol_fails(self) -> None:
        with self.assertRaisesRegex(ContractError, "unknown symbol"):
            self.validate(FIXTURES / "invalid" / "unknown_symbol.csv")

    def test_duplicate_rows_fail(self) -> None:
        with self.assertRaisesRegex(ContractError, "duplicate ticker-session"):
            self.validate(FIXTURES / "invalid" / "duplicate.csv")

    def test_future_rows_fail(self) -> None:
        with self.assertRaisesRegex(ContractError, "future session"):
            self.validate(FIXTURES / "invalid" / "future.csv")

    def test_cross_ticker_substitution_fails(self) -> None:
        with self.assertRaisesRegex(ContractError, "cross-ticker substitution"):
            self.validate(FIXTURES / "invalid" / "cross_ticker.csv")

    def mutate_valid_csv(self, mutator) -> Path:
        handle = tempfile.NamedTemporaryFile("w", newline="", encoding="utf-8", suffix=".csv", delete=False)
        handle.close()
        output = Path(handle.name)
        with VALID_CSV.open(newline="", encoding="utf-8") as source:
            reader = csv.DictReader(source)
            fields = list(reader.fieldnames or [])
            rows = list(reader)
        fields, rows = mutator(fields, rows)
        with output.open("w", newline="", encoding="utf-8") as target:
            writer = csv.DictWriter(target, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
        self.addCleanup(output.unlink, missing_ok=True)
        return output

    def test_unexpected_fields_fail(self) -> None:
        def mutate(fields, rows):
            fields.append("synthetic_flag")
            for row in rows:
                row["synthetic_flag"] = "false"
            return fields, rows
        with self.assertRaisesRegex(ContractError, "fields or field order"):
            self.validate(self.mutate_valid_csv(mutate))

    def test_weekend_rows_fail(self) -> None:
        def mutate(fields, rows):
            rows[0]["session_date"] = "2026-05-30"
            return fields, rows
        with self.assertRaisesRegex(ContractError, "weekend session"):
            self.validate(self.mutate_valid_csv(mutate))

    def test_nonpositive_prices_fail(self) -> None:
        def mutate(fields, rows):
            rows[0]["adjusted_close"] = "0"
            return fields, rows
        with self.assertRaisesRegex(ContractError, "invalid adjusted_close"):
            self.validate(self.mutate_valid_csv(mutate))

    def test_invalid_ohlc_relationship_fails(self) -> None:
        def mutate(fields, rows):
            rows[0]["adjusted_high"] = "19.5"
            return fields, rows
        with self.assertRaisesRegex(ContractError, "adjusted_high invariant"):
            self.validate(self.mutate_valid_csv(mutate))


if __name__ == "__main__":
    unittest.main()
