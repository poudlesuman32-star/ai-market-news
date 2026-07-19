from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/ppi-r10-source-period-command.yml"


class R10SourcePeriodCommandTests(unittest.TestCase):
    def test_command_is_exact_and_owner_only(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("github.event.issue.number == 55", text)
        self.assertIn("github.event.issue.pull_request == null", text)
        self.assertIn("github.event.comment.body == '/ppi-r10-source-period-collect'", text)
        self.assertIn("github.event.comment.user.login == 'poudlesuman32-star'", text)
        self.assertIn("github.event.pull_request.user.login == 'poudlesuman32-star'", text)
        self.assertIn("github.event.pull_request.head.repo.full_name == github.repository", text)

    def test_reviewed_pull_request_validates_one_exact_request_without_checkout(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("pull_request:\n    branches: [main]", text)
        self.assertIn("automation_requests/r10-source-period/*.json", text)
        self.assertIn("startsWith(github.event.pull_request.head.ref, 'automation/request-r10-source-period-')", text)
        self.assertIn("pulls/${REQUEST_PR}/files", text)
        self.assertIn("assert len(files) == 1", text)
        self.assertIn("collect_and_validate_source_period", text)
        self.assertNotIn("actions/checkout", text)

    def test_dispatches_current_main_workflow_only(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("gh workflow run verify-primary-source-coverage.yml", text)
        self.assertIn('--repo "$GITHUB_REPOSITORY"', text)
        self.assertIn("--ref main", text)
        self.assertIn("actions: write", text)
        self.assertIn("contents: read", text)
        self.assertIn("pull-requests: read", text)
        self.assertNotIn("contents: write", text)
        self.assertNotIn("pull-requests: write", text)
        self.assertNotIn("git push", text)
        self.assertNotIn("gh pr create", text)
        self.assertNotIn("gh pr merge", text)
        self.assertNotIn("repository_dispatch", text)

    def test_receipt_preserves_downstream_safety_boundaries(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn('"publication_authorized": False', text)
        self.assertIn('"repository_mutation_authorized": False', text)
        self.assertIn('"trading_authorized": False', text)
        self.assertIn("actions/upload-artifact@v4", text)
        self.assertIn("retention-days: 30", text)


if __name__ == "__main__":
    unittest.main()
