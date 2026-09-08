from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "validate_ppi_public_3000_snapshot_contract.py"
SPEC = importlib.util.spec_from_file_location("step9_validator", SCRIPT)
validator = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(validator)


class Step9SnapshotContractTests(unittest.TestCase):
    def make_record(self, index: int, allocated: bool = True) -> dict:
        figi = f"BBG{index:09d}"
        disposition = "allocated" if allocated else "deferred_unmatched"
        return {
            "candidate_id": f"ppi-sec-seed-{index:024x}",
            "cik": f"{index + 1:010d}",
            "ticker": f"T{index:04d}",
            "exchange": "NASDAQ",
            "disposition": disposition,
            "instrument_id": validator.stable_instrument_id(figi) if allocated else None,
            "figi": figi if allocated else None,
            "identity_status": "verified_exact_figi" if allocated else "deferred_unmatched",
            "classification_status": "unresolved_asset_subtype",
            "source_row_sha256": f"{index:064x}",
        }

    def write_success(self, root: Path, records: list[dict]) -> None:
        allocated = [v for v in records if v["disposition"] == "allocated"]
        deferred = [v for v in records if v["disposition"] != "allocated"]
        for name, values in (
            ("universe-instruments-3000.jsonl", allocated),
            ("universe-deferred-3000.jsonl", deferred),
        ):
            payload = b"".join(validator.canon(v) for v in values)
            (root / name).write_bytes(payload)
        (root / "manifest.json").write_text("{}\n", encoding="utf-8")
        (root / "receipt.json").write_text("{}\n", encoding="utf-8")
        (root / "report.md").write_text("# fixture\n", encoding="utf-8")

    def test_machine_contract_is_fail_closed(self) -> None:
        contract = validator.validate_contract(ROOT / "contracts" / "PPI-PUBLIC-3000-SNAPSHOT-001-R1.json")
        self.assertFalse(contract["entry_gate"]["live_execution_authorized"])
        self.assertFalse(contract["authority"]["network_access"])
        self.assertFalse(contract["authority"]["provider_acquisition"])
        self.assertEqual(contract["required_total_candidate_dispositions"], 3000)

    def test_stable_id_reuses_existing_namespace(self) -> None:
        figi = "BBG000000001"
        expected = validator.stable_instrument_id(figi)
        self.assertTrue(expected.startswith("ppi-us-equity-"))
        record = self.make_record(1)
        record["figi"] = figi
        record["instrument_id"] = expected
        validator.validate_record(record)

    def test_rejects_guessed_classification(self) -> None:
        record = self.make_record(1)
        record["classification_status"] = "common_stock"
        with self.assertRaises(validator.ContractError):
            validator.validate_record(record)

    def test_rejects_schema_invalid_candidate_id(self) -> None:
        record = self.make_record(1)
        record["candidate_id"] = "candidate-0001"
        with self.assertRaises(validator.ContractError):
            validator.validate_record(record)

    def test_rejects_extra_record_field(self) -> None:
        record = self.make_record(1)
        record["producer_note"] = "unexpected"
        with self.assertRaises(validator.ContractError):
            validator.validate_record(record)

    def test_rejects_invalid_identity_scalars(self) -> None:
        for field, bad_value in (("cik", "123"), ("ticker", "bad ticker"), ("exchange", "OTC")):
            record = self.make_record(1)
            record[field] = bad_value
            with self.subTest(field=field), self.assertRaises(validator.ContractError):
                validator.validate_record(record)

    def test_deferred_record_never_gets_instrument_id(self) -> None:
        record = self.make_record(1, allocated=False)
        record["instrument_id"] = "ppi-us-equity-" + "a" * 24
        with self.assertRaises(validator.ContractError):
            validator.validate_record(record)

    def test_exact_3000_fixture_passes_offline(self) -> None:
        records = [self.make_record(i, allocated=(i % 7 != 0)) for i in range(3000)]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_success(root, records)
            result = validator.validate_snapshot(root)
        self.assertEqual(result["total_candidate_dispositions"], 3000)
        self.assertTrue(result["gate_passed"])

    def test_wrong_count_fails_closed(self) -> None:
        records = [self.make_record(i) for i in range(2999)]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_success(root, records)
            with self.assertRaises(validator.ContractError):
                validator.validate_snapshot(root)

    def test_duplicate_candidate_fails_closed(self) -> None:
        records = [self.make_record(i) for i in range(3000)]
        records[-1]["candidate_id"] = records[0]["candidate_id"]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_success(root, records)
            with self.assertRaises(validator.ContractError):
                validator.validate_snapshot(root)

    def test_unexpected_path_fails_closed(self) -> None:
        records = [self.make_record(i) for i in range(3000)]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_success(root, records)
            (root / "raw-provider.json").write_text("{}\n", encoding="utf-8")
            with self.assertRaises(validator.ContractError):
                validator.validate_snapshot(root)

    def test_blocked_artifact_has_no_partial_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "blocked.json").write_text(json.dumps({"status": "blocked"}) + "\n", encoding="utf-8")
            (root / "report.md").write_text("# blocked\n", encoding="utf-8")
            result = validator.validate_snapshot(root)
        self.assertEqual(result["artifact_mode"], "blocked")
        self.assertFalse(result["gate_passed"])


if __name__ == "__main__":
    unittest.main()
