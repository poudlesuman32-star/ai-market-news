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

    def test_progress_report_uses_exact_machine_checkable_shape(self) -> None:
        report = module.build_progress_report(
            blocker_class="reviewer_or_validator_bug",
            canonical_step=8,
            evidence=["workflow_run:30915460990", "error:source_run_identity_name"],
            safe_actions_taken=["prepare_code_patch", "prepare_tests"],
            approval_required_for=["merge_pull_request", "provider_acquisition"],
            next_safe_action="inspect hosted zero-network CI",
            contract=self.contract,
        )
        self.assertEqual(set(report), module.REPORT_FIELDS)
        module.validate_progress_report(report, contract=self.contract)

    def test_progress_report_rejects_step_outside_26_step_plan(self) -> None:
        for step in (0, 27):
            with self.assertRaises(module.PolicyError):
                module.build_progress_report(
                    blocker_class="ci_policy_or_trigger",
                    canonical_step=step,
                    evidence=["missing hosted run"],
                    safe_actions_taken=["inspect_workflow_results"],
                    approval_required_for=[],
                    next_safe_action="inspect repository Actions policy",
                    contract=self.contract,
                )

    def test_progress_report_rejects_unsafe_action_as_safe_action_taken(self) -> None:
        with self.assertRaises(module.PolicyError):
            module.build_progress_report(
                blocker_class="provider_or_quota_gate",
                canonical_step=8,
                evidence=["replacement artifact required"],
                safe_actions_taken=["provider_acquisition"],
                approval_required_for=["provider_acquisition"],
                next_safe_action="request explicit approval",
                contract=self.contract,
            )

    def test_progress_report_rejects_globally_safe_action_not_safe_for_blocker_class(self) -> None:
        self.assertIn("prepare_masking_patch", self.contract["safe_preparation_actions"])
        self.assertNotIn(
            "prepare_masking_patch",
            self.contract["blocker_classes"]["ci_policy_or_trigger"]["safe_actions"],
        )
        with self.assertRaises(module.PolicyError):
            module.build_progress_report(
                blocker_class="ci_policy_or_trigger",
                canonical_step=8,
                evidence=["workflow not scheduled"],
                safe_actions_taken=["prepare_masking_patch"],
                approval_required_for=[],
                next_safe_action="inspect repository Actions policy",
                contract=self.contract,
            )

    def test_progress_report_rejects_non_fenced_approval_action(self) -> None:
        with self.assertRaises(module.PolicyError):
            module.build_progress_report(
                blocker_class="ci_policy_or_trigger",
                canonical_step=8,
                evidence=["workflow not scheduled"],
                safe_actions_taken=["inspect_workflow_results"],
                approval_required_for=["invent_new_authority"],
                next_safe_action="inspect repository Actions policy",
                contract=self.contract,
            )

    def test_no_progress_report_must_use_anti_loop_status(self) -> None:
        report = module.build_progress_report(
            blocker_class="ci_policy_or_trigger",
            canonical_step=8,
            evidence=[],
            safe_actions_taken=[],
            approval_required_for=[],
            next_safe_action="no_new_safe_progress",
            contract=self.contract,
        )
        self.assertEqual(report["next_safe_action"], "no_new_safe_progress")
        with self.assertRaises(module.PolicyError):
            module.build_progress_report(
                blocker_class="ci_policy_or_trigger",
                canonical_step=8,
                evidence=[],
                safe_actions_taken=[],
                approval_required_for=[],
                next_safe_action="repeat previous status",
                contract=self.contract,
            )

    def test_document_explicitly_preserves_canonical_order_and_approval_fence(self) -> None:
        text = DOC.read_text(encoding="utf-8")
        self.assertIn("does not change canonical backlog order", text)
        self.assertIn("replacement provider acquisition", text)
        self.assertIn("explicit approval", text)
        self.assertIn("no_new_safe_progress", text)
        self.assertIn("selected blocker class", text)
        for field in module.REPORT_FIELDS:
            self.assertIn(field, text)


if __name__ == "__main__":
    unittest.main()
