from pathlib import Path
import unittest


class R9CompactDispatchRetryWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.workflow = Path('.github/workflows/ppi-r9-compact-dispatch-retry.yml').read_text(encoding='utf-8')

    def test_retries_only_failed_main_publication_runs(self) -> None:
        self.assertIn('PPI R9 automated publication and private dispatch', self.workflow)
        self.assertIn("github.event.workflow_run.conclusion == 'failure'", self.workflow)
        self.assertIn("github.event.workflow_run.head_branch == 'main'", self.workflow)
        self.assertIn("github.event.workflow_run.event == 'workflow_run'", self.workflow)

    def test_exact_artifact_and_frozen_contract_are_bound(self) -> None:
        self.assertIn('ppi-r9-automated-publication-${PUBLICATION_RUN_ID}-${PUBLICATION_RUN_ATTEMPT}', self.workflow)
        self.assertIn('actions/artifacts/${artifact_id}/zip', self.workflow)
        self.assertIn('publication_authorization.json', self.workflow)
        self.assertIn('PPI-R9-AUTONOMY-002', self.workflow)
        self.assertIn('2f29d15d2f4447c2f17327277614c274e051c2259b34af054ee6daa1553ff704', self.workflow)

    def test_dispatch_uses_exact_ten_property_envelope_and_input_file(self) -> None:
        self.assertIn("require(len(client_payload) == 10", self.workflow)
        self.assertIn("'transaction_json': transaction_json", self.workflow)
        self.assertIn("'authorization_request_sha256': authorization['authorization_request_sha256']", self.workflow)
        self.assertIn("'public_commit': report['public_commit']", self.workflow)
        self.assertIn('--input retry-evidence/dispatch_request.json', self.workflow)
        self.assertNotIn('client_payload[source_workflow_run_id]', self.workflow)

    def test_retry_cannot_republish_or_enable_prohibited_actions(self) -> None:
        self.assertNotIn('publish_public_news_snapshot.sh', self.workflow)
        self.assertNotIn('contents: write', self.workflow)
        self.assertNotIn('git push', self.workflow)
        self.assertNotIn('MMM', self.workflow)
        self.assertNotIn('broker', self.workflow.lower())
        self.assertNotIn('trading', self.workflow.lower())
        self.assertIn("authorization.get('prohibited_actions_enabled') is False", self.workflow)

    def test_retry_evidence_is_retained(self) -> None:
        self.assertIn('dispatch_request.json', self.workflow)
        self.assertIn('retry_binding.json', self.workflow)
        self.assertIn('retention-days: 90', self.workflow)
        self.assertIn('if-no-files-found: error', self.workflow)


if __name__ == '__main__':
    unittest.main()
