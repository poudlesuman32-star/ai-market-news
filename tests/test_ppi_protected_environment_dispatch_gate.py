from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import ppi_migration_autopilot_v5 as v5  # noqa: E402


class ProtectedEnvironmentDispatchGateTests(unittest.TestCase):
    def test_missing_environment_holds_public_dispatch(self) -> None:
        with mock.patch.object(v5, "_api", return_value=(404, None)):
            ready, detail = v5.protected_environment_ready("token")
        self.assertFalse(ready)
        self.assertIn("is not configured", detail)

    def test_administrator_bypass_holds_public_dispatch(self) -> None:
        environment = {
            "can_admins_bypass": True,
            "deployment_branch_policy": {
                "protected_branches": True,
                "custom_branch_policies": False,
            },
        }
        with mock.patch.object(v5, "_api", return_value=(200, environment)):
            ready, detail = v5.protected_environment_ready("token")
        self.assertFalse(ready)
        self.assertIn("administrator bypass", detail)

    def test_missing_custom_protection_rule_holds_public_dispatch(self) -> None:
        environment = {
            "can_admins_bypass": False,
            "deployment_branch_policy": {
                "protected_branches": True,
                "custom_branch_policies": False,
            },
        }
        with mock.patch.object(
            v5,
            "_api",
            side_effect=[
                (200, environment),
                (200, {"total_count": 0, "custom_deployment_protection_rules": []}),
            ],
        ):
            ready, detail = v5.protected_environment_ready("token")
        self.assertFalse(ready)
        self.assertIn("no custom deployment protection rule", detail)

    def test_identified_custom_protection_rule_allows_normal_dispatch_gate(self) -> None:
        environment = {
            "can_admins_bypass": False,
            "deployment_branch_policy": {
                "protected_branches": True,
                "custom_branch_policies": False,
            },
        }
        rules = {
            "total_count": 1,
            "custom_deployment_protection_rules": [
                {"id": 71, "app": {"id": 9001, "slug": "ppi-independent-gate"}},
            ],
        }
        with (
            mock.patch.object(v5, "_api", side_effect=[(200, environment), (200, rules)]),
            mock.patch.object(v5, "ORIGINAL_PUBLIC_DISPATCH_GATE", return_value=(True, "quota window clear")) as original,
        ):
            allowed, detail = v5.guarded_public_dispatch_gate("token", "a" * 40)
        self.assertTrue(allowed)
        self.assertIn("protected environment", detail)
        original.assert_called_once_with("token", "a" * 40)

    def test_guard_does_not_call_normal_dispatch_gate_when_environment_is_not_ready(self) -> None:
        with (
            mock.patch.object(v5, "_api", return_value=(404, None)),
            mock.patch.object(v5, "ORIGINAL_PUBLIC_DISPATCH_GATE") as original,
        ):
            allowed, _ = v5.guarded_public_dispatch_gate("token", "a" * 40)
        self.assertFalse(allowed)
        original.assert_not_called()


if __name__ == "__main__":
    unittest.main()
