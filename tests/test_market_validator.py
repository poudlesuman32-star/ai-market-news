import json
import tempfile
import unittest
from pathlib import Path

from scripts.contract_common import ContractError
from scripts.validate_market_artifact import validate_market_artifact, validate_market_artifact_at_commit
from tests.iteration3_fixture import COLLECTION_CONFIG, SNAPSHOT_PATH, SYMBOLS_CONFIG, TODAY
from tests.iteration3_git import create_three_commit_repo


class MarketArtifactValidatorTests(unittest.TestCase):
    def validate_disk(self, root: Path, data_commit: str):
        return validate_market_artifact(
            repository_root=root,
            snapshot_path=SNAPSHOT_PATH,
            expected_data_commit=data_commit,
            symbols_config=SYMBOLS_CONFIG,
            collection_config=COLLECTION_CONFIG,
            today=TODAY,
        )

    def test_complete_snapshot_validates_on_disk_and_at_public_commit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            commits = create_three_commit_repo(root)
            self.validate_disk(root, commits["data_commit"])
            validation = validate_market_artifact_at_commit(
                repository_root=root,
                public_commit=commits["public_commit"],
                snapshot_path=SNAPSHOT_PATH,
                expected_data_commit=commits["data_commit"],
                symbols_config=SYMBOLS_CONFIG,
                collection_config=COLLECTION_CONFIG,
                today=TODAY,
            )
            self.assertEqual(validation.summary.row_count, 11)

    def test_tampered_csv_and_replaced_receipt_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            commits = create_three_commit_repo(root)
            csv_path = root / SNAPSHOT_PATH / "market_prices.csv"
            csv_path.write_text(csv_path.read_text() + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ContractError, "hash mismatch"):
                self.validate_disk(root, commits["data_commit"])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            commits = create_three_commit_repo(root)
            receipt_path = root / SNAPSHOT_PATH / "collection_receipt.json"
            receipt = json.loads(receipt_path.read_text())
            receipt["csv_sha256"] = "0" * 64
            receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
            with self.assertRaisesRegex(ContractError, "receipt CSV hash mismatch"):
                self.validate_disk(root, commits["data_commit"])

    def test_incorrect_data_commit_missing_file_and_extra_file_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            commits = create_three_commit_repo(root)
            with self.assertRaisesRegex(ContractError, "manifest data commit"):
                self.validate_disk(root, "f" * 40)
            manifest_path = root / SNAPSHOT_PATH / "market_artifact_manifest.json"
            manifest_path.unlink()
            with self.assertRaisesRegex(ContractError, "exactly the three"):
                self.validate_disk(root, commits["data_commit"])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            commits = create_three_commit_repo(root)
            (root / SNAPSHOT_PATH / "unexpected.txt").write_text("nope", encoding="utf-8")
            with self.assertRaisesRegex(ContractError, "exactly the three"):
                self.validate_disk(root, commits["data_commit"])

    def test_unsafe_snapshot_path_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            commits = create_three_commit_repo(root)
            with self.assertRaisesRegex(ContractError, "parent path"):
                validate_market_artifact(
                    repository_root=root,
                    snapshot_path="snapshots/../outside",
                    expected_data_commit=commits["data_commit"],
                    symbols_config=SYMBOLS_CONFIG,
                    collection_config=COLLECTION_CONFIG,
                    today=TODAY,
                )


if __name__ == "__main__":
    unittest.main()
