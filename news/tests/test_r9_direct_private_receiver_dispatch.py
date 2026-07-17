from pathlib import Path
import unittest


class DirectPrivateReceiverDispatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.workflow = Path(
            '.github/workflows/ppi-r9-direct-private-receiver-dispatch.yml'
        ).read_text(encoding='utf-8')

    def test_bridge_binds_exact_successful_publication_run(self) -> None:
        self.assertIn('name: PPI R9 direct private receiver dispatch', self.workflow)
        self.assertIn('workflow_run:', self.workflow)
        self.assertIn('- PPI R9 automated publication and private dispatch', self.workflow)
        self.assertIn("github.event.workflow_run.conclusion == 'success'", self.workflow)
        self.assertIn("github.event.workflow_run.head_branch == 'main'", self.workflow)
        self.assertIn('.github/workflows/ppi-r9-automated-publication.yml', self.workflow)
        self.assertIn("run['path'] == os.environ['EXPECTED_PUBLICATION_WORKFLOW_PATH']", self.workflow)
        self.assertIn("run['status'] == 'completed' and run['conclusion'] == 'success'", self.workflow)

    def test_bridge_downloads_one_exact_publication_artifact(self) -> None:
        self.assertIn(
            'ppi-r9-automated-publication-${PUBLICATION_RUN_ID}-${PUBLICATION_RUN_ATTEMPT}',
            self.workflow,
        )
        self.assertIn('actions/runs/${PUBLICATION_RUN_ID}/artifacts', self.workflow)
        self.assertIn('actions/artifacts/${artifact_id}/zip', self.workflow)
        self.assertIn("item.get('name') == os.environ['ARTIFACT_NAME']", self.workflow)
        self.assertIn("item.get('expired') is False", self.workflow)
        self.assertIn('for attempt in 1 2 3 4 5 6', self.workflow)
        self.assertIn('private_dispatch_request.json', self.workflow)
        self.assertNotIn('while true', self.workflow)

    def test_bridge_converts_exact_compact_payload_to_workflow_dispatch(self) -> None:
        self.assertIn("assert set(source) == {'event_type', 'client_payload'}", self.workflow)
        self.assertIn("source['event_type'] == 'ppi_public_snapshot_ready'", self.workflow)
        self.assertIn("request = {'ref': 'main', 'inputs': inputs}", self.workflow)
        self.assertIn("assert isinstance(inputs, dict) and set(inputs) == expected", self.workflow)
        self.assertIn("assert all(isinstance(value, str) and value for value in inputs.values())", self.workflow)
        self.assertIn('ppi-r9-private-receiver.yml', self.workflow)
        self.assertIn('/actions/workflows/${PRIVATE_RECEIVER_WORKFLOW_FILE}/dispatches', self.workflow)
        self.assertNotIn('repos/${EXPECTED_PRIVATE_REPOSITORY}/dispatches', self.workflow)

    def test_bridge_has_no_publication_or_prohibited_authority(self) -> None:
        self.assertIn('actions: read', self.workflow)
        self.assertIn('contents: read', self.workflow)
        self.assertNotIn('contents: write', self.workflow)
        self.assertNotIn('git push', self.workflow)
        self.assertNotIn('MMM', self.workflow)
        self.assertNotIn('broker', self.workflow.lower())
        self.assertNotIn('trading', self.workflow.lower())


if __name__ == '__main__':
    unittest.main()
