import importlib.util
from pathlib import Path
import tempfile
import unittest

_SPEC = importlib.util.spec_from_file_location(
    "prepare_runtime",
    Path(__file__).resolve().parents[2] / "tools/prepare-local-runtime.py",
)
module = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(module)


class PrepareRuntimeTests(unittest.TestCase):
    def test_generates_private_secrets_and_preserves_existing_credentials(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "runtime"
            self.assertEqual(2, len(module.prepare(root)))
            password = root / "secrets/postgres-password"
            original = password.read_bytes()
            self.assertGreater(len(original), 40)
            self.assertEqual(0o600, password.stat().st_mode & 0o777)
            self.assertEqual([], module.prepare(root))
            self.assertEqual(original, password.read_bytes())

    def test_rejects_secret_symlink_without_modifying_target(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "secrets").mkdir()
            target = root / "external"
            target.write_text("unchanged")
            (root / "secrets/postgres-password").symlink_to(target)
            with self.assertRaises(ValueError):
                module.prepare(root)
            self.assertEqual("unchanged", target.read_text())

    def test_rejects_empty_existing_secret(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "secrets").mkdir()
            (root / "secrets/postgres-password").touch()
            with self.assertRaises(ValueError):
                module.prepare(root)
