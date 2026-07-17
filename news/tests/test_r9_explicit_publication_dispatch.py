from pathlib import Path
import unittest


class ExplicitR9PublicationDispatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.collector = Path('.github/workflows/collect-public-news-live-auto.yml').read_text(encoding='utf-8')
        cls.publisher = Path('.github/workflows/ppi-r9-automated-publication.yml').read_text(encoding='utf-8')

    def test_collector_dispatches_only_after_dual_validation(self) -> None:
        agreement = self.collector.index('Require two-validator candidate agreement')
        dispatch = self.collector.index('Explicitly dispatch exact candidate to publication workflow')
        self.assertLess(agreement, dispatch)
        self.assertIn('actions: write', self.collector)
        self.assertIn('ppi-r9-automated-publication.yml/dispatches', self.collector)
        self.assertNotIn('ppi-r9-explicit-publication.yml/dispatches', self.collector)
        self.assertIn('inputs[source_workflow_run_id]=${GITHUB_RUN_ID}', self.collector)
        self.assertIn('inputs[source_workflow_run_attempt]=${GITHUB_RUN_ATTEMPT}', self.collector)
        self.assertNotIn('schedule:', self.collector)
        self.assertNotIn('cron:', self.collector)

    def test_accepted_publication_workflow_has_exact_explicit_inputs(self) -> None:
        self.assertIn('workflow_dispatch:', self.publisher)
        self.assertIn('source_workflow_run_id:', self.publisher)
        self.assertIn('source_workflow_run_attempt:', self.publisher)
        self.assertIn('actions/runs/${SOURCE_RUN_ID}', self.publisher)
        self.assertIn('ppi-readonly-live-candidate-${SOURCE_RUN_ID}-${SOURCE_RUN_ATTEMPT}', self.publisher)
        self.assertIn("assert source['name'] == 'PPI automated read-only live primary-source candidate'", self.publisher)
        self.assertIn("assert source['event'] == 'workflow_dispatch'", self.publisher)
        self.assertIn("assert source['status'] == 'completed' and source['conclusion'] == 'success'", self.publisher)
        self.assertIn("assert source['head_branch'] == 'main'", self.publisher)
        self.assertIn("assert receipt['source_commit'] == os.environ['SOURCE_HEAD_SHA']", self.publisher)
        self.assertIn("assert independent['candidate_valid'] is True", self.publisher)

    def test_readonly_candidate_has_no_legacy_workflow_run_trigger(self) -> None:
        workflow_run_block = self.publisher.split('workflow_run:', 1)[1].split('workflow_dispatch:', 1)[0]
        self.assertIn('PPI public news live primary-source preview', workflow_run_block)
        self.assertNotIn('PPI automated read-only live primary-source candidate', workflow_run_block)
        self.assertFalse(Path('.github/workflows/ppi-r9-explicit-publication.yml').exists())

    def test_frozen_contract_and_private_dispatch_precede_no_prohibited_actions(self) -> None:
        contract = self.publisher.index('Bind exact frozen autonomy contract')
        publish = self.publisher.index('Publish immutable Commit A B C transaction')
        private_dispatch = self.publisher.index('Dispatch exact transaction to private validator')
        self.assertLess(contract, publish)
        self.assertLess(publish, private_dispatch)
        self.assertIn('PPI-R9-AUTONOMY-002', self.publisher)
        self.assertIn("'prohibited_actions_enabled': False", self.publisher)
        self.assertIn('ppi-r9-automated-publication-${{ github.run_id }}-${{ github.run_attempt }}', self.publisher)
        self.assertNotIn('MMM', self.publisher)
        self.assertNotIn('broker', self.publisher.lower())
        self.assertNotIn('trading', self.publisher.lower())


if __name__ == '__main__':
    unittest.main()
