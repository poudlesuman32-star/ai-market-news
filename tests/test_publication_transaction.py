import tempfile
import unittest
from pathlib import Path

from scripts.verify_publication_transaction import verify_publication_transaction
from tests.iteration3_fixture import COLLECTION_CONFIG, SNAPSHOT_PATH, SYMBOLS_CONFIG, TODAY
from tests.iteration3_git import create_three_commit_repo, run_git


class PublicationTransactionTests(unittest.TestCase):
    def verify(self, root: Path, commits: dict[str, str]):
        return verify_publication_transaction(
            repository_root=root,
            previous_head=commits["foundation"],
            data_commit=commits["data_commit"],
            public_commit=commits["public_commit"],
            pointer_commit=commits["pointer_commit"],
            snapshot_path=SNAPSHOT_PATH,
            latest_file=root / "latest.json",
            symbols_config=SYMBOLS_CONFIG,
            collection_config=COLLECTION_CONFIG,
            today=TODAY,
        )

    def test_valid_three_commit_transaction_passes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            commits = create_three_commit_repo(root)
            result = self.verify(root, commits)
            self.assertEqual(result["data_commit"], commits["data_commit"])
            self.assertEqual(result["public_commit"], commits["public_commit"])
            self.assertEqual(result["pointer_commit"], commits["pointer_commit"])
            self.assertEqual(result["snapshot_path"], SNAPSHOT_PATH)

    def test_modified_working_pointer_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            commits = create_three_commit_repo(root)
            (root / "latest.json").write_text("{}\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "does not match pointer commit"):
                self.verify(root, commits)

    def test_extra_commit_cannot_be_used_as_pointer_commit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            commits = create_three_commit_repo(root)
            (root / "README.md").write_text("unexpected change\n", encoding="utf-8")
            run_git(root, "add", "README.md")
            run_git(root, "commit", "-m", "unexpected fourth commit")
            commits["pointer_commit"] = run_git(root, "rev-parse", "HEAD")
            with self.assertRaisesRegex(ValueError, "pointer commit must directly descend"):
                self.verify(root, commits)

    def test_wrong_previous_head_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            commits = create_three_commit_repo(root)
            commits["foundation"] = commits["public_commit"]
            with self.assertRaisesRegex(ValueError, "data commit must directly descend"):
                self.verify(root, commits)


if __name__ == "__main__":
    unittest.main()
