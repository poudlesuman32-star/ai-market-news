from pathlib import Path
import unittest


class AutomatedR9PublicationWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.workflow = Path('.github/workflows/ppi-r9-automated-publication.yml').read_text(encoding='utf-8')

    def test_exact_preview_workflow_run_trigger(self) -> None:
        self.assertIn('name: PPI R9 automated publication and private dispatch', self.workflow)
        self.assertIn('workflow_run:', self.workflow)
        self.assertIn('workflows: ["PPI public news live primary-source preview"]', self.workflow)
        self.assertIn("github.event.workflow_run.conclusion == 'success'", self.workflow)
        self.assertIn("github.event.workflow_run.head_branch == 'main'", self.workflow)

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
        self.assertIn('event_type=ppi_public_snapshot_ready', self.workflow)
        self.assertIn('client_payload[pointer_commit]', self.workflow)
        self.assertIn('client_payload[contract_sha256]', self.workflow)


if __name__ == '__main__':
    unittest.main()
