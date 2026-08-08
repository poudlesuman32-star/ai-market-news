from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts/resolve_sec_user_agent.py"
WORKFLOW_PATH = ROOT / ".github/workflows/ppi-sec-universe-pilot.yml"

spec = importlib.util.spec_from_file_location("resolver", SCRIPT_PATH)
assert spec and spec.loader
resolver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(resolver)


class SecUserAgentResolverTests(unittest.TestCase):
    def owner_file(self, root: Path, email: object) -> Path:
        path = root / "owner.json"
        path.write_text(json.dumps({"login": "owner", "email": email}) + "\n", encoding="utf-8")
        return path

    def test_repository_contact_variable_has_priority(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = resolver.resolve(
                "operations@ppi-research.org",
                self.owner_file(root, "profile@ppi-research.org"),
            )
            self.assertTrue(result["resolved"])
            self.assertEqual(result["source"], "repository_contact_variable")
            self.assertEqual(
                result["user_agent"],
                "PPI Universe Research operations@ppi-research.org",
            )

    def test_public_profile_email_is_automatic_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = resolver.resolve("", self.owner_file(root, "owner@ppi-research.org"))
            self.assertTrue(result["resolved"])
            self.assertEqual(result["source"], "github_public_profile")
            self.assertEqual(result["application_name"], "PPI Universe Research")

    def test_missing_contact_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = resolver.resolve("", self.owner_file(root, None))
            self.assertFalse(result["resolved"])
            self.assertEqual(result["status"], "blocked")
            self.assertNotIn("user_agent", result)

    def test_rejects_noreply_and_placeholder_addresses(self) -> None:
        for value in (
            "12345+owner@users.noreply.github.com",
            "noreply@ppi-research.org",
            "ops@example.com",
            "ops@research.example.org",
            "invalid",
        ):
            with self.subTest(value=value):
                with self.assertRaises(resolver.ResolverError):
                    resolver.validate_email(value)

    def test_cli_writes_user_agent_to_github_environment_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            owner = self.owner_file(root, "owner@ppi-research.org")
            github_env = root / "env"
            github_output = root / "output"
            old_argv = list(__import__("sys").argv)
            try:
                __import__("sys").argv = [
                    str(SCRIPT_PATH),
                    "--owner-json", str(owner),
                    "--configured-email", "",
                    "--github-env", str(github_env),
                    "--github-output", str(github_output),
                ]
                self.assertEqual(resolver.main(), 0)
            finally:
                __import__("sys").argv = old_argv
            env_text = github_env.read_text(encoding="utf-8")
            output_text = github_output.read_text(encoding="utf-8")
            self.assertIn("PPI_SEC_USER_AGENT=PPI Universe Research owner@ppi-research.org", env_text)
            self.assertIn("resolved=true", output_text)
            self.assertNotIn("owner@ppi-research.org", output_text)

    def test_workflow_uses_automatic_resolver_without_full_user_agent_variable(self) -> None:
        text = WORKFLOW_PATH.read_text(encoding="utf-8")
        self.assertIn("scripts/resolve_sec_user_agent.py", text)
        self.assertIn("users/${GITHUB_REPOSITORY_OWNER}", text)
        self.assertIn("vars.PPI_SEC_CONTACT_EMAIL", text)
        self.assertNotIn("vars.PPI_SEC_USER_AGENT", text)
        self.assertIn("--blocked-if-missing-user-agent", text)
        for forbidden in (
            "secrets.",
            "contents: write",
            "issues: write",
            "pull-requests: write",
            "musksuman3/ai-signal-engine",
        ):
            self.assertNotIn(forbidden, text)

    def test_workflow_masks_contact_before_validation_and_collection(self) -> None:
        text = WORKFLOW_PATH.read_text(encoding="utf-8")
        mask_step = text.index("- name: Mask configured SEC contact")
        validation_step = text.index("- name: Validate code and boundaries")
        resolver_step = text.index("- name: Resolve declared SEC user agent automatically")
        collection_step = text.index("- name: Collect or report unresolved SEC contact")
        self.assertLess(mask_step, validation_step)
        self.assertLess(mask_step, resolver_step)
        self.assertLess(mask_step, collection_step)
        self.assertIn("printf '::add-mask::%s\\n' \"$PPI_SEC_CONTACT_EMAIL\"", text)
        self.assertIn(
            "printf '::add-mask::PPI Universe Research %s\\n' \"$PPI_SEC_CONTACT_EMAIL\"",
            text,
        )


if __name__ == "__main__":
    unittest.main()
