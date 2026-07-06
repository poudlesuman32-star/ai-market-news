import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_latest_pointer import build_latest_pointer
from scripts.contract_common import ContractError
from tests.iteration3_fixture import COLLECTION_CONFIG, SNAPSHOT_PATH, SYMBOLS_CONFIG, TODAY
from tests.iteration3_git import create_three_commit_repo, run_git


class LatestPointerBuilderTests(unittest.TestCase):
    def test_three_commit_sequence_and_pointer_are_exact(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            commits = create_three_commit_repo(root)
            pointer = json.loads((root / "latest.json").read_text())
            self.assertEqual(pointer["data_commit"], commits["data_commit"])
            self.assertEqual(pointer["public_commit"], commits["public_commit"])
            self.assertFalse(pointer["target_window_complete"])
            files_at_public = run_git(root, "ls-tree", "-r", "--name-only", commits["public_commit"], "--", SNAPSHOT_PATH).splitlines()
            self.assertEqual(
                sorted(files_at_public),
                sorted(
                    [
                        f"{SNAPSHOT_PATH}/market_prices.csv",
                        f"{SNAPSHOT_PATH}/collection_receipt.json",
                        f"{SNAPSHOT_PATH}/market_artifact_manifest.json",
                    ]
                ),
            )
            changed_in_c = run_git(root, "diff-tree", "--no-commit-id", "--name-only", "-r", commits["pointer_commit"]).splitlines()
            self.assertEqual(changed_in_c, ["latest.json"])

    def test_invalid_shas_same_commits_wrong_target_and_false_completion_claim_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            commits = create_three_commit_repo(root)
            common = dict(
                repository_root=root,
                snapshot_path=SNAPSHOT_PATH,
                symbols_config=SYMBOLS_CONFIG,
                collection_config=COLLECTION_CONFIG,
                today=TODAY,
            )
            with self.assertRaisesRegex(ContractError, "40-character"):
                build_latest_pointer(data_commit="abc", public_commit=commits["public_commit"], target_end_date="2026-07-24", **common)
            with self.assertRaisesRegex(ContractError, "must be different"):
                build_latest_pointer(data_commit=commits["data_commit"], public_commit=commits["data_commit"], target_end_date="2026-07-24", **common)
            with self.assertRaisesRegex(ContractError, "unexpected target"):
                build_latest_pointer(data_commit=commits["data_commit"], public_commit=commits["public_commit"], target_end_date="2026-07-25", **common)
            with self.assertRaisesRegex(ContractError, "completion state"):
                build_latest_pointer(
                    data_commit=commits["data_commit"],
                    public_commit=commits["public_commit"],
                    target_end_date="2026-07-24",
                    expected_complete=True,
                    **common,
                )

    def test_public_commit_without_manifest_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            commits = create_three_commit_repo(root)
            with self.assertRaisesRegex(ContractError, "exact complete snapshot"):
                build_latest_pointer(
                    repository_root=root,
                    snapshot_path=SNAPSHOT_PATH,
                    data_commit=commits["foundation"],
                    public_commit=commits["data_commit"],
                    target_end_date="2026-07-24",
                    symbols_config=SYMBOLS_CONFIG,
                    collection_config=COLLECTION_CONFIG,
                    today=TODAY,
                )


if __name__ == "__main__":
    unittest.main()
