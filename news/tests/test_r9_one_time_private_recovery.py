import json
from pathlib import Path
import unittest


class OneTimePrivateRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.workflow = Path(
            '.github/workflows/ppi-r9-one-time-private-recovery.yml'
        ).read_text(encoding='utf-8')
        cls.marker = json.loads(
            Path('.github/r9-recovery/29549106843-2.json').read_text(encoding='utf-8')
        )

    def test_marker_binds_exact_successful_publication_attempt(self) -> None:
        self.assertEqual(self.marker['publication_workflow_run_id'], '29549106843')
        self.assertEqual(self.marker['publication_workflow_run_attempt'], '2')
        self.assertEqual(
            self.marker['publication_artifact_name'],
            'ppi-r9-automated-publication-29549106843-2',
        )
        self.assertEqual(
            self.marker['publication_artifact_sha256'],
            '9c8d84b1e48417dcc57be869564d0b154b9965bcb4c89d78d10a796db4eb00d9',
        )
        self.assertEqual(
            self.marker['data_commit'],
            'e204fbc1eb72f04429786e6bb5ca96f6007c3912',
        )
        self.assertEqual(
            self.marker['pointer_commit'],
            'be672de0f77c9ec140b63e437593310bd718643f',
        )
        self.assertEqual(self.marker['status'], 'pending_exact_recovery')

    def test_recovery_runs_only_for_exact_marker_push(self) -> None:
        self.assertIn('push:', self.workflow)
        self.assertIn('branches: [main]', self.workflow)
        self.assertIn('.github/r9-recovery/29549106843-2.json', self.workflow)
        self.assertNotIn('schedule:', self.workflow)
        self.assertNotIn('workflow_dispatch:', self.workflow)

    def test_recovery_verifies_exact_run_artifact_and_transaction(self) -> None:
        self.assertIn("run['path'] == os.environ['EXPECTED_PUBLICATION_WORKFLOW_PATH']", self.workflow)
        self.assertIn("run['status'] == 'completed' and run['conclusion'] == 'success'", self.workflow)
        self.assertIn("artifact.get('digest') == 'sha256:' + os.environ['PUBLICATION_ARTIFACT_SHA256']", self.workflow)
        self.assertIn("assert set(source) == {'event_type', 'client_payload'}", self.workflow)
        self.assertIn("source['event_type'] == 'ppi_public_snapshot_ready'", self.workflow)
        self.assertIn("inputs['data_commit'] == os.environ['RECOVERY_DATA_COMMIT']", self.workflow)
        self.assertIn("inputs['pointer_commit'] == os.environ['RECOVERY_POINTER_COMMIT']", self.workflow)

    def test_recovery_is_idempotent_and_dispatches_new_receiver_interface(self) -> None:
        self.assertIn('audit/r9_official_run_registry.json?ref=main', self.workflow)
        self.assertIn("'already_registered': registered", self.workflow)
        self.assertIn("'dispatch_required': not registered", self.workflow)
        self.assertIn("if: env.RECOVERY_NEEDED == 'true'", self.workflow)
        self.assertIn('ppi-r9-private-receiver.yml', self.workflow)
        self.assertIn('/actions/workflows/${PRIVATE_RECEIVER_WORKFLOW_FILE}/dispatches', self.workflow)
        self.assertIn("request = {'ref': 'main', 'inputs': inputs}", self.workflow)
        self.assertNotIn('repos/${EXPECTED_PRIVATE_REPOSITORY}/dispatches', self.workflow)

    def test_recovery_has_no_publication_or_prohibited_authority(self) -> None:
        self.assertIn('actions: read', self.workflow)
        self.assertIn('contents: read', self.workflow)
        self.assertNotIn('contents: write', self.workflow)
        self.assertNotIn('git push', self.workflow)
        self.assertNotIn('MMM', self.workflow)
        self.assertNotIn('broker', self.workflow.lower())
        self.assertNotIn('trading', self.workflow.lower())
        self.assertIn("'r10_enabled': False", self.workflow)


if __name__ == '__main__':
    unittest.main()
