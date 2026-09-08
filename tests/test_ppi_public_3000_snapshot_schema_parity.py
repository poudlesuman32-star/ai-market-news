from __future__ import annotations

import importlib.util
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas" / "ppi_public_3000_snapshot.schema.json"
VALIDATOR_PATH = ROOT / "scripts" / "validate_ppi_public_3000_snapshot_contract.py"
SPEC = importlib.util.spec_from_file_location("step9_validator", VALIDATOR_PATH)
validator = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(validator)


class Step9SchemaParityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        cls.properties = cls.schema["properties"]

    def test_closed_record_shape_matches_validator(self) -> None:
        self.assertFalse(self.schema["additionalProperties"])
        self.assertEqual(set(self.schema["required"]), validator.RECORD_FIELDS)

    def test_identity_patterns_match_validator(self) -> None:
        expected = {
            "candidate_id": validator.CANDIDATE_ID.pattern,
            "cik": validator.CIK.pattern,
            "ticker": validator.TICKER.pattern,
            "instrument_id": validator.INSTRUMENT_ID.pattern,
            "figi": validator.FIGI.pattern,
            "source_row_sha256": validator.HEX64.pattern,
        }
        for field, pattern in expected.items():
            self.assertEqual(self.properties[field]["pattern"], pattern)
            re.compile(self.properties[field]["pattern"])

    def test_exchange_allowlist_matches_validator(self) -> None:
        self.assertEqual(set(self.properties["exchange"]["enum"]), validator.EXCHANGES)

    def test_disposition_and_identity_states_match_validator(self) -> None:
        self.assertEqual(
            set(self.properties["disposition"]["enum"]),
            {"allocated", "deferred_ambiguous", "deferred_unmatched"},
        )
        self.assertEqual(
            set(self.properties["identity_status"]["enum"]),
            {"verified_exact_figi", "deferred_ambiguous", "deferred_unmatched"},
        )
        self.assertEqual(self.properties["classification_status"]["const"], "unresolved_asset_subtype")

    def test_allocated_conditional_matches_validator(self) -> None:
        conditional = self.schema["allOf"][0]
        self.assertEqual(conditional["if"]["properties"]["disposition"]["const"], "allocated")
        then = conditional["then"]["properties"]
        self.assertEqual(then["instrument_id"]["pattern"], validator.INSTRUMENT_ID.pattern)
        self.assertEqual(then["figi"]["pattern"], validator.FIGI.pattern)
        self.assertEqual(then["identity_status"]["const"], "verified_exact_figi")
        self.assertEqual(conditional["else"]["properties"]["instrument_id"]["type"], "null")


if __name__ == "__main__":
    unittest.main()
