"""First-run setup token: a public deployment cannot be claimed by its first visitor.

Run from the project folder:
    python -m unittest tests.test_setup_token -v
"""
import importlib
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PASSWORD = "SetupToken#Password2026"


class SetupTokenTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="fc_setup_"))
        shutil.copytree(REPO / "forenchain", self.root / "forenchain",
                        ignore=shutil.ignore_patterns("__pycache__"))
        for name in list(sys.modules):
            if name == "forenchain" or name.startswith("forenchain."):
                del sys.modules[name]
        sys.path.insert(0, str(self.root))
        self.auth = importlib.import_module("forenchain.auth")
        self.saved = os.environ.pop("FORENCHAIN_SETUP_TOKEN", None)

    def tearDown(self):
        os.environ.pop("FORENCHAIN_SETUP_TOKEN", None)
        if self.saved is not None:
            os.environ["FORENCHAIN_SETUP_TOKEN"] = self.saved
        sys.path.remove(str(self.root))
        for name in list(sys.modules):
            if name == "forenchain" or name.startswith("forenchain."):
                del sys.modules[name]
        shutil.rmtree(self.root, ignore_errors=True)

    def test_wrong_or_missing_token_is_refused(self):
        os.environ["FORENCHAIN_SETUP_TOKEN"] = "correct-horse-battery-staple"
        self.assertTrue(self.auth.setup_token_configured())
        for token in (None, "", "wrong"):
            with self.subTest(token=token):
                with self.assertRaises(PermissionError):
                    self.auth.create_initial_admin("admin01", PASSWORD, token)
        self.assertTrue(self.auth.initial_admin_required())

    def test_correct_token_creates_admin_once(self):
        os.environ["FORENCHAIN_SETUP_TOKEN"] = "correct-horse-battery-staple"
        self.auth.create_initial_admin("admin01", PASSWORD, "correct-horse-battery-staple")
        self.assertFalse(self.auth.initial_admin_required())
        with self.assertRaises(ValueError):
            self.auth.create_initial_admin("admin02", PASSWORD, "correct-horse-battery-staple")

    def test_no_token_configured_reports_unlocked_for_cli_only(self):
        self.assertFalse(self.auth.setup_token_configured())
        self.auth.create_initial_admin("admin01", PASSWORD)  # local command line path
        self.assertFalse(self.auth.initial_admin_required())


if __name__ == "__main__":
    unittest.main(verbosity=2)
