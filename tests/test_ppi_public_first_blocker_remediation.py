from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "classify_ppi_public_first_blocker.py"
CONTRACT = ROOT / "contracts" / "PPI-PUBLIC-FIRST-BLOCKER-REMEDIATION-001-R1.json"
DOC = ROOT / "docs" / "architecture" / "PPI_PUBLIC_FIRST_BLOCKER_REMEDIATION.md"

spec = importlib.util.spec_from_file_location("blocker_policy", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)


class BlockerRemediationPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = json.loads(CONTRACT.read_text(encoding="utf-8"))

    def test_contract_validates_and_grants_zero_execution_authority(self) -> None:
        module.validate_contract(self.contract)
        self.assertTrue(self.contract["authority"])
        self.assertFalse(any(self.contract["authority"].values()))

    def test_all_expected_blocker_classes_are_frozen(self) -> None:
        self.assertEqual(
            set(self.contract["blocker_classes"]),
            {
                "ci_policy_or_trigger",
                "reviewer_or_validator_bug",
                "expired_or_missing_artifact",
                "log_hygiene_or_secret_exposure",
                "stale_documentation_or_ledger",
                "merge_conflict_or_stale_branch",
                "provider_or_quota_gate",
                "private_recovery_or_billing_gate",
                "registry_publication_or_trading_gate",
            },
        )

    def test_safe_offline_preparation_is_allowed(self) -> None:
        result = module.classify(
            "reviewer_or_validator_bug", "prepare_tests", contract=self.contract
        )
        self.assertTrue(result["allowed"])
        self.assertEqual(result["decision"], "safe_preparation_allowed")

    def test_provider_acquisition_always_stops_for_explicit_approval(self) -> None:
        for blocker_class in self.contract["blocker_classes"]:
            result = module.classify(
                blocker_class, "provider_acquisition", contract=self.contract
            )
            self.assertFalse(result["allowed"])
            self.assertEqual(result["decision"], "stop_for_explicit_approval")

    def test_merge_always_stops_for_explicit_approval(self) -> None:
        for blocker_class in self.contract["blocker_classes"]:
            result = module.classify(
                blocker_class, "merge_pull_request", contract=self.contract
            )
            self.assertFalse(result["allowed"])
            self.assertEqual(result["decision"], "stop_for_explicit_approval")

    def test_private_billing_registry_publication_and_trading_are_fenced(self) -> None:
        actions = {
            "private_recovery",
            "private_dispatch",
            "alter_billing",
            "private_provider_access",
            "mutate_registry",
            "publish_production_output",
            "enable_broker_authority",
            "enable_order_authority",
            "enable_trading_authority",
        }
        for action in actions:
            result = module.classify(
                "stale_documentation_or_ledger", action, contract=self.contract
            )
            self.assertFalse(result["allowed"], action)
            self.assertEqual(result["decision"], "stop_for_explicit_approval")

    def test_unlisted_action_fails_closed(self) -> None:
        result = module.classify(
            "ci_policy_or_trigger", "invent_new_authority", contract=self.contract
        )
        self.assertFalse(result["allowed"])
        self.assertEqual(result["decision"], "not_allowlisted")

    def test_unknown_blocker_class_fails_closed(self) -> None:
        with self.assertRaises(module.PolicyError):
            module.classify("mystery_blocker", "prepare_tests", contract=self.contract)

    def test_anti_loop_policy_is_frozen(self) -> None:
        self.assertEqual(
            self.contract["anti_loop"],
            {
                "require_new_evidence_or_safe_change": True,
                "duplicate_prs_for_same_blocker_forbidden": True,
                "no_progress_status": "no_new_safe_progress",
            },
        )

    def test_document_explicitly_preserves_canonical_order_and_approval_fence(self) -> None:
        text = DOC.read_text(encoding="utf-8")
        self.assertIn("does not change canonical backlog order", text)
        self.assertIn("replacement provider acquisition", text)
        self.assertIn("explicit approval", text)
        self.assertIn("no_new_safe_progress", text)


if __name__ == "__main__":
    unittest.main()
