from pathlib import Path
import unittest


class AutomatedR9PublicationWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.workflow = Path('.github/workflows/ppi-r9-automated-publication.yml').read_text(encoding='utf-8')

    def test_supported_candidate_workflow_run_triggers(self) -> None:
        self.assertIn('name: PPI R9 automated publication and private dispatch', self.workflow)
        self.assertIn('workflow_run:', self.workflow)
        self.assertIn('- PPI public news live primary-source preview', self.workflow)
        self.assertIn('- PPI automated read-only live primary-source candidate', self.workflow)
        self.assertIn("github.event.workflow_run.conclusion == 'success'", self.workflow)
        self.assertIn("github.event.workflow_run.head_branch == 'main'", self.workflow)

    def test_exact_artifact_mapping_fails_closed(self) -> None:
        self.assertIn('ppi-public-news-live-preview-${SOURCE_RUN_ID}-${SOURCE_RUN_ATTEMPT}', self.workflow)
        self.assertIn('ppi-readonly-live-candidate-${SOURCE_RUN_ID}-${SOURCE_RUN_ATTEMPT}', self.workflow)
        self.assertIn('Unsupported R9 source workflow', self.workflow)
        self.assertIn("assert source['name'] in allowed_workflows", self.workflow)
        self.assertIn("assert source['name'] == os.environ['SOURCE_WORKFLOW_NAME']", self.workflow)

    def test_artifact_api_download_is_exact_bounded_and_retained(self) -> None:
        self.assertIn('actions/runs/${SOURCE_RUN_ID}/artifacts', self.workflow)
        self.assertIn('actions/artifacts/${artifact_id}/zip', self.workflow)
        self.assertIn("artifact.get('name') == os.environ['ARTIFACT_NAME']", self.workflow)
        self.assertIn("artifact.get('expired') is False", self.workflow)
        self.assertIn('for attempt in 1 2 3 4 5 6', self.workflow)
        self.assertIn('Exact candidate artifact not yet retrievable', self.workflow)
        self.assertIn('sleep 10', self.workflow)
        self.assertIn("'download_method': 'exact_artifact_id_api'", self.workflow)
        self.assertIn("'failure_stage': 'candidate_artifact_download'", self.workflow)
        self.assertIn("'fail_closed': True", self.workflow)
        self.assertIn('download_failure.json', self.workflow)
        self.assertNotIn('gh run download', self.workflow)
        self.assertNotIn('while true', self.workflow)

    def test_frozen_contract_and_mixed_provider_gate_precede_publication(self) -> None:
        contract = self.workflow.index('Bind exact frozen autonomy contract')
        publish = self.workflow.index('Publish immutable Commit A B C transaction')
        self.assertLess(contract, publish)
        self.assertIn('2f29d15d2f4447c2f17327277614c274e051c2259b34af054ee6daa1553ff704', self.workflow)
        self.assertIn("provider_counts'].get('sec_edgar', 0)", self.workflow)
        self.assertIn("provider_counts'].get('official_company_source', 0)", self.workflow)
        self.assertIn("receipt['provider_failures'] == []", self.workflow)

    def test_no_manual_environment_gate_or_prohibited_actions(self) -> None:
        self.assertNotIn('environment: ppi-r9-manual-approval', self.workflow)
        self.assertIn("'manual_approval_required': False", self.workflow)
        self.assertIn("'prohibited_actions_enabled': False", self.workflow)
        self.assertNotIn('manual_authorization.json', self.workflow)
        self.assertNotIn('ppi-r9-manual-publication', self.workflow)
        self.assertIn('publication_authorization.json', self.workflow)
        self.assertIn('ppi-r9-automated-publication-', self.workflow)
        self.assertNotIn('MMM', self.workflow)
        self.assertNotIn('broker', self.workflow.lower())
        self.assertNotIn('trading', self.workflow.lower())

    def test_credentials_are_ephemeral_and_dispatch_is_exact(self) -> None:
        self.assertIn('persist-credentials: false', self.workflow)
        self.assertIn('Remove ephemeral authentication', self.workflow)
        self.assertIn("'event_type': 'ppi_public_snapshot_ready'", self.workflow)
        self.assertIn("'transaction_json': transaction_json", self.workflow)
        self.assertIn('assert len(client_payload) == 10', self.workflow)
        self.assertIn('private_dispatch_request.json', self.workflow)
        self.assertIn('--input publication-evidence/private_dispatch_request.json', self.workflow)
        for field in (
            'source_workflow_name',
            'source_workflow_run_id',
            'source_workflow_run_attempt',
            'source_head_sha',
            'candidate_sha256',
            'authorization_request_sha256',
            'publication_workflow_run_id',
            'publication_workflow_run_attempt',
            'data_commit',
            'public_commit',
            'pointer_commit',
            'snapshot_path',
            'contract_id',
            'contract_sha256',
        ):
            self.assertIn(f"'{field}':", self.workflow)
        self.assertNotIn('client_payload[source_workflow_name]', self.workflow)
        self.assertNotIn('client_payload[public_commit]', self.workflow)


if __name__ == '__main__':
    unittest.main()
