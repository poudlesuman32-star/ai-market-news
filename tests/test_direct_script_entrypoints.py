import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class DirectScriptEntrypointTests(unittest.TestCase):
    def test_cli_scripts_resolve_package_imports_when_run_by_path(self):
        scripts = (
            "scripts/collect_market_window.py",
            "scripts/validate_market_contract.py",
            "scripts/build_market_manifest.py",
            "scripts/validate_market_artifact.py",
            "scripts/build_latest_pointer.py",
        )
        for script in scripts:
            with self.subTest(script=script):
                result = subprocess.run(
                    [sys.executable, script, "--help"],
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(
                    result.returncode,
                    0,
                    msg=f"{script} failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}",
                )
                self.assertNotIn("ModuleNotFoundError", result.stderr)


if __name__ == "__main__":
    unittest.main()
