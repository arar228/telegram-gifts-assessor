"""Offline checks: execute credential initialization only, never Telegram clients."""

import ast
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from credentials_config import ConfigurationError, load_telegram_credentials

ROOT = Path(__file__).resolve().parents[1]


class CredentialsConfigTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)

    def supply_credentials(self):
        os.environ.update(API_ID="12345", API_HASH="a" * 32)

    def test_configured_credentials_are_preserved(self):
        self.supply_credentials()
        self.assertEqual(load_telegram_credentials(), (12345, "a" * 32))

    def test_missing_id_has_clear_error(self):
        with self.assertRaisesRegex(ConfigurationError, "API_ID"):
            load_telegram_credentials()

    def test_missing_hash_has_clear_error(self):
        os.environ["API_ID"] = "12345"
        with self.assertRaisesRegex(ConfigurationError, "API_HASH"):
            load_telegram_credentials()

    def test_invalid_id_excludes_supplied_value(self):
        self.supply_credentials()
        for value in ("synthetic-invalid-id", "0", "-1", " "):
            with self.subTest(value=value):
                os.environ["API_ID"] = value
                with self.assertRaises(ConfigurationError) as caught:
                    load_telegram_credentials()
                self.assertIn("API_ID", str(caught.exception))
                self.assertNotIn("synthetic-invalid-id", str(caught.exception))

    def test_invalid_hash_excludes_supplied_value(self):
        self.supply_credentials()
        for value in ("synthetic-invalid-hash", "b" * 31, "g" * 32, " "):
            with self.subTest(length=len(value)):
                os.environ["API_HASH"] = value
                with self.assertRaises(ConfigurationError) as caught:
                    load_telegram_credentials()
                self.assertIn("API_HASH", str(caught.exception))
                self.assertNotIn("synthetic-invalid-hash", str(caught.exception))

    def test_optional_phone_does_not_gate_configuration(self):
        self.supply_credentials()
        self.assertNotIn("PHONE_NUMBER", os.environ)
        self.assertEqual(load_telegram_credentials()[0], 12345)

    def test_entrypoints_initialize_from_helper_only(self):
        self.supply_credentials()
        for filename in ("price_checker.py", "test_gifts.py"):
            with self.subTest(filename=filename):
                module = ast.parse((ROOT / filename).read_text(encoding="utf-8"))
                assignments = []
                helper_import = None
                for node in module.body:
                    if isinstance(node, ast.ImportFrom) and node.module == "credentials_config":
                        helper_import = node
                    if isinstance(node, ast.Assign):
                        names = {child.id for target in node.targets for child in ast.walk(target)
                                 if isinstance(child, ast.Name)}
                        if names & {"API_ID", "API_HASH"}:
                            self.assertEqual(names, {"API_ID", "API_HASH"})
                            self.assertIsInstance(node.value, ast.Call)
                            self.assertEqual(node.value.func.id, "load_telegram_credentials")
                            self.assertEqual(node.value.args, [])
                            assignments.append(node)
                self.assertIsNotNone(helper_import)
                self.assertEqual(len(assignments), 1)
                # Deliberately compile only these two safe AST nodes, not the app.
                initialization = ast.Module(body=[helper_import, assignments[0]], type_ignores=[])
                namespace = {}
                exec(compile(initialization, filename, "exec"), namespace)
                self.assertEqual(namespace["API_ID"], 12345)
                self.assertEqual(namespace["API_HASH"], "a" * 32)


if __name__ == "__main__":
    unittest.main()
