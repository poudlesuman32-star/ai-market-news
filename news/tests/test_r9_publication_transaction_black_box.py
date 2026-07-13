from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


class R9PublicationTransactionBlackBoxTests(unittest.TestCase):
    def run_command(
        self,
        command: list[str],
        *,
        cwd: Path,
        env: dict[str, str] | None = None,
        check: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(command, cwd=cwd, env=env, text=True, capture_output=True, check=False)
        if check and result.returncode != 0:
            self.fail(f"command failed: {command}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}")
        return result

    def git(self, repository: Path, *arguments: str) -> str:
        return self.run_command(["git", *arguments], cwd=repository).stdout.strip()

    def read_github_env(self, path: Path) -> dict[str, str]:
        values: dict[str, str] = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            key, separator, value = line.partition("=")
            self.assertEqual(separator, "=", line)
            values[key] = value
        return values

    def write_candidate(self, root: Path) -> tuple[Path, Path, str]:
        news = root / "candidate-news.jsonl"
        records = [
            {
                "record_id": "record-sec-1",
                "event_id": "event-sec-1",
                "provider": "sec_edgar",
                "ticker": "NVDA",
                "published_at_utc": "2026-07-13T14:00:00Z",
                "validation": "transformed_valid",
                "synthetic_content_used": False,
                "source_content_modified": False,
            },
            {
                "record_id": "record-company-1",
                "event_id": "event-company-1",
                "provider": "official_company_source",
                "ticker": "MSFT",
                "published_at_utc": "2026-07-13T14:05:00Z",
                "validation": "transformed_valid",
                "synthetic_content_used": False,
                "source_content_modified": False,
            },
        ]
        news.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in records), encoding="utf-8")
        digest = hashlib.sha256(news.read_bytes()).hexdigest()
        receipt = root / "collection_receipt.json"
        receipt.write_text(
            json.dumps(
                {
                    "schema_version": "1.1.0",
                    "run_id": "black-box-source-run",
                    "collection_mode": "live_primary_sources",
                    "source_repository": "poudlesuman32-star/ai-market-news",
                    "source_commit": "a" * 40,
                    "generated_at_utc": "2026-07-13T14:10:00Z",
                    "collection_complete": True,
                    "record_count": 2,
                    "event_count": 2,
                    "provider_count": 2,
                    "provider_counts": {"official_company_source": 1, "sec_edgar": 1},
                    "providers": ["official_company_source", "sec_edgar"],
                    "tickers": ["MSFT", "NVDA"],
                    "input_file": "news.jsonl",
                    "dataset_sha256": digest,
                    "request_counts": {"sec": 1, "official_company_sources": 1, "polygon": 0, "finnhub": 0},
                    "provider_failures": [],
                    "synthetic_content_used": False,
                    "source_content_modified": False,
                    "private_content_excluded": True,
                },
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        return news, receipt, digest

    def publication_environment(
        self,
        *,
        root: Path,
        work: Path,
        news: Path,
        receipt: Path,
        run_id: str,
        source_root: Path,
    ) -> dict[str, str]:
        runner_temp = root / f"runner-{run_id}"
        runner_temp.mkdir()
        environment = dict(os.environ)
        environment.update(
            {
                "GITHUB_REF": "refs/heads/main",
                "GITHUB_REPOSITORY": "poudlesuman32-star/ai-market-news",
                "GITHUB_RUN_ID": run_id,
                "GITHUB_RUN_ATTEMPT": "1",
                "GITHUB_SHA": self.git(work, "rev-parse", "main"),
                "GITHUB_ENV": str(root / f"github-env-{run_id}"),
                "GITHUB_STEP_SUMMARY": str(root / f"summary-{run_id}.md"),
                "RUNNER_TEMP": str(runner_temp),
                "NEWS_FILE": str(news),
                "COLLECTION_RECEIPT_FILE": str(receipt),
                "DATA_BRANCH": "public-news-data",
                "GATE_FILE": str(source_root / "news/config/public_news_preview_gate.json"),
                "PYTHONPATH": str(source_root / "news/src"),
            }
        )
        return environment

    def test_commit_abc_bytes_and_exact_retry_resume(self) -> None:
        source_root = Path(__file__).resolve().parents[2]
        script = source_root / "scripts/publish_public_news_snapshot.sh"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            remote = root / "remote.git"
            work = root / "work"
            self.run_command(["git", "init", "--bare", str(remote)], cwd=root)
            self.run_command(["git", "init", "-b", "main", str(work)], cwd=root)
            self.git(work, "config", "user.name", "black-box-validator")
            self.git(work, "config", "user.email", "black-box@example.invalid")
            (work / "README.md").write_text("public news test repository\n", encoding="utf-8")
            self.git(work, "add", "README.md")
            self.git(work, "commit", "-m", "initial main")
            self.git(work, "remote", "add", "origin", str(remote))
            self.git(work, "push", "-u", "origin", "main")
            self.git(work, "checkout", "-b", "public-news-data")
            (work / "branch.txt").write_text("public-news-data\n", encoding="utf-8")
            self.git(work, "add", "branch.txt")
            self.git(work, "commit", "-m", "initialize public data branch")
            self.git(work, "push", "-u", "origin", "public-news-data")
            previous_head = self.git(work, "rev-parse", "HEAD")
            self.git(work, "checkout", "main")

            news, receipt, digest = self.write_candidate(root)
            first_env = self.publication_environment(
                root=root,
                work=work,
                news=news,
                receipt=receipt,
                run_id="12345678",
                source_root=source_root,
            )
            self.run_command(["bash", str(script)], cwd=work, env=first_env)
            first_persisted = self.read_github_env(Path(first_env["GITHUB_ENV"]))

            self.git(work, "fetch", "origin", "public-news-data")
            pointer_commit = self.git(work, "rev-parse", "origin/public-news-data")
            public_commit = self.git(work, "rev-parse", f"{pointer_commit}^")
            data_commit = self.git(work, "rev-parse", f"{public_commit}^")
            self.assertEqual(self.git(work, "rev-parse", f"{data_commit}^"), previous_head)
            self.assertEqual(first_persisted["DATA_COMMIT"], data_commit)
            self.assertEqual(first_persisted["PUBLIC_COMMIT"], public_commit)
            self.assertEqual(first_persisted["POINTER_COMMIT"], pointer_commit)
            self.assertEqual(first_persisted["PREVIOUS_PUBLISHED_HEAD"], previous_head)
            self.assertEqual(first_persisted["REMOTE_PUBLISHED_HEAD"], pointer_commit)
            self.assertEqual(first_persisted["PUBLICATION_REUSED"], "false")

            data_paths = set(self.git(work, "diff-tree", "--no-commit-id", "--name-only", "-r", data_commit).splitlines())
            manifest_paths = set(self.git(work, "diff-tree", "--no-commit-id", "--name-only", "-r", public_commit).splitlines())
            pointer_paths = set(self.git(work, "diff-tree", "--no-commit-id", "--name-only", "-r", pointer_commit).splitlines())
            self.assertEqual(pointer_paths, {"latest.json"})
            self.assertEqual(len(manifest_paths), 1)
            self.assertTrue(next(iter(manifest_paths)).endswith("/news_manifest.json"))
            self.assertEqual(len(data_paths), 2)
            self.assertTrue(any(path.endswith("/news.jsonl") for path in data_paths))
            self.assertTrue(any(path.endswith("/collection_receipt.json") for path in data_paths))

            latest = json.loads(self.git(work, "show", f"{pointer_commit}:latest.json"))
            snapshot_path = latest["snapshot_path"]
            published_news = self.run_command(
                ["git", "show", f"{pointer_commit}:{snapshot_path}/news.jsonl"], cwd=work
            ).stdout.encode("utf-8")
            self.assertEqual(published_news, news.read_bytes())
            manifest = json.loads(self.git(work, "show", f"{pointer_commit}:{snapshot_path}/news_manifest.json"))
            self.assertEqual(manifest["data_commit"], data_commit)
            self.assertEqual(manifest["news_file_sha256"], digest)
            self.assertEqual(latest["data_commit"], data_commit)
            self.assertEqual(latest["public_commit"], public_commit)
            self.assertNotIn("pointer_commit", latest)

            second_env = self.publication_environment(
                root=root,
                work=work,
                news=news,
                receipt=receipt,
                run_id="12345679",
                source_root=source_root,
            )
            self.run_command(["bash", str(script)], cwd=work, env=second_env)
            second_persisted = self.read_github_env(Path(second_env["GITHUB_ENV"]))
            self.assertEqual(second_persisted["DATA_COMMIT"], data_commit)
            self.assertEqual(second_persisted["PUBLIC_COMMIT"], public_commit)
            self.assertEqual(second_persisted["POINTER_COMMIT"], pointer_commit)
            self.assertEqual(second_persisted["SNAPSHOT_PATH"], snapshot_path)
            self.assertEqual(second_persisted["PREVIOUS_PUBLISHED_HEAD"], previous_head)
            self.assertEqual(second_persisted["REMOTE_PUBLISHED_HEAD"], pointer_commit)
            self.assertEqual(second_persisted["PUBLICATION_REUSED"], "true")
            self.git(work, "fetch", "origin", "public-news-data")
            self.assertEqual(self.git(work, "rev-parse", "origin/public-news-data"), pointer_commit)

            second_report = json.loads(
                (Path(second_persisted["ARTIFACT_ROOT"]) / "run_report.json").read_text(encoding="utf-8")
            )
            self.assertTrue(second_report["publication_reused"])
            self.assertFalse(second_report["publication_push_performed"])
            self.assertEqual(second_report["data_commit"], data_commit)
            self.assertEqual(second_report["public_commit"], public_commit)
            self.assertEqual(second_report["pointer_commit"], pointer_commit)


if __name__ == "__main__":
    unittest.main()
