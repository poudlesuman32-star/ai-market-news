import tempfile
import unittest
from pathlib import Path

from scripts.build_market_manifest import build_market_manifest
from scripts.contract_common import ContractError, market_artifact_id, sha256
from tests.iteration3_fixture import COLLECTION_CONFIG, SNAPSHOT_PATH, SYMBOLS_CONFIG, TODAY, write_data_files
from tests.iteration3_git import init_repo, run_git


class MarketManifestBuilderTests(unittest.TestCase):
    def test_builder_derives_all_integrity_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_repo(root)
            snapshot = write_data_files(root)
            run_git(root, "add", SNAPSHOT_PATH)
            run_git(root, "commit", "-m", "data")
            data_commit = run_git(root, "rev-parse", "HEAD")
            csv_path = snapshot / "market_prices.csv"
            manifest = build_market_manifest(
                data_file=csv_path,
                data_file_path=f"{SNAPSHOT_PATH}/market_prices.csv",
                provider_name="Fixture Provider",
                source_repository=COLLECTION_CONFIG["source_repository"],
                source_commit_sha=data_commit,
                symbols_config=SYMBOLS_CONFIG,
                collection_config=COLLECTION_CONFIG,
                today=TODAY,
            )
            self.assertEqual(manifest["data_file_sha256"], sha256(csv_path))
            self.assertEqual(manifest["row_count"], 11)
            self.assertEqual(manifest["symbol_count"], 11)
            self.assertEqual(manifest["start_date"], "2026-05-29")
            self.assertEqual(manifest["end_date"], "2026-05-29")
            self.assertFalse(manifest["synthetic_prices_used"])
            self.assertFalse(manifest["source_data_modified"])
            self.assertEqual(
                manifest["artifact_id"],
                market_artifact_id(
                    source_repository=manifest["source_repository"],
                    source_commit_sha=data_commit,
                    data_file_path=manifest["data_file_path"],
                    data_file_sha256=manifest["data_file_sha256"],
                ),
            )

    def test_builder_rejects_unsafe_path_and_abbreviated_commit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            snapshot = write_data_files(root)
            common = dict(
                data_file=snapshot / "market_prices.csv",
                provider_name="Fixture Provider",
                source_repository=COLLECTION_CONFIG["source_repository"],
                symbols_config=SYMBOLS_CONFIG,
                collection_config=COLLECTION_CONFIG,
                today=TODAY,
            )
            with self.assertRaisesRegex(ContractError, "parent path"):
                build_market_manifest(data_file_path="snapshots/../market_prices.csv", source_commit_sha="a" * 40, **common)
            with self.assertRaisesRegex(ContractError, "40 lowercase"):
                build_market_manifest(data_file_path=f"{SNAPSHOT_PATH}/market_prices.csv", source_commit_sha="abc123", **common)


if __name__ == "__main__":
    unittest.main()
