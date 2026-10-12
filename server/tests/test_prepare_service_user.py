"""Private credentials retain permissions while Compose adopts their owner."""
import importlib.util
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

PATH = Path(__file__).resolve().parents[2] / "tools/prepare-local-runtime.py"
SPEC = importlib.util.spec_from_file_location("prepare_runtime_service_user", PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class PrepareServiceUserTests(unittest.TestCase):
    def test_private_secrets_and_existing_environment_are_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            MODULE.prepare(root / "runtime", root / "database")
            env = root / ".env"
            env.write_text(
                '# existing settings\nOTHER="keep # value"\nexport WAKFU_SERVICE_UID = 1000 # owner\nWAKFU_SERVICE_GID=1000\n'
            )
            before = {
                name: (root / "database/secrets" / name).read_bytes()
                for name in MODULE.SECRET_NAMES
            }
            uid, gid = MODULE.configure_service_user(root / "database", env)
            self.assertEqual((uid, gid), (os.getuid(), os.getgid()))
            self.assertEqual(
                env.read_text(),
                '# existing settings\nOTHER="keep # value"\n'
                f"export WAKFU_SERVICE_UID = {uid} # owner\nWAKFU_SERVICE_GID={gid}\n",
            )
            MODULE.configure_service_user(root / "database", env)
            for name, contents in before.items():
                path = root / "database/secrets" / name
                self.assertEqual(path.read_bytes(), contents)
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_missing_keys_append_without_destroying_last_line(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            MODULE.prepare(root / "runtime", root / "database")
            env = root / ".env"
            env.write_text("OTHER=preserved")
            uid, gid = MODULE.configure_service_user(root / "database", env)
            self.assertEqual(
                env.read_text(),
                f"OTHER=preserved\nWAKFU_SERVICE_UID={uid}\nWAKFU_SERVICE_GID={gid}\n",
            )

    def test_different_secret_owners_fail_without_environment_write(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            MODULE.prepare(root / "runtime", root / "database")
            env = root / ".env"
            env.write_text("OTHER=preserved\n")
            actual = Path.stat

            def stat(path, *args, **kwargs):
                result = actual(path, *args, **kwargs)
                if path.name == "ecology-token":
                    return SimpleNamespace(
                        st_mode=result.st_mode,
                        st_uid=result.st_uid + 1,
                        st_gid=result.st_gid,
                    )
                return result

            with patch.object(Path, "stat", stat):
                with self.assertRaisesRegex(ValueError, "owners differ"):
                    MODULE.configure_service_user(root / "database", env)
            self.assertEqual(env.read_text(), "OTHER=preserved\n")
