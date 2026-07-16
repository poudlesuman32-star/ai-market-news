from pathlib import Path
import unittest


class R9CandidateWorkflowIdentityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.workflow = Path('.github/workflows/collect-public-news-live-auto.yml').read_text(encoding='utf-8')

    def test_runtime_identity_matches_canonical_workflow_name(self) -> None:
        canonical = 'PPI automated read-only live primary-source candidate'
        self.assertIn(f'name: {canonical}', self.workflow)
        self.assertIn(f'run-name: {canonical}', self.workflow)
        self.assertNotIn('run-name: Automated live candidate', self.workflow)

    def test_candidate_artifact_identity_is_stable(self) -> None:
        self.assertIn(
            'ppi-readonly-live-candidate-${{ github.run_id }}-${{ github.run_attempt }}',
            self.workflow,
        )


if __name__ == '__main__':
    unittest.main()
