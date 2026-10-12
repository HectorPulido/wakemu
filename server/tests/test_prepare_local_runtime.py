import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

_ROOT = Path(__file__).resolve().parents[2]
_SPEC = importlib.util.spec_from_file_location(
    "prepare_runtime", _ROOT / "tools/prepare-local-runtime.py"
)
module = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(module)


class PrepareRuntimeTests(unittest.TestCase):
    def test_runtime_recreation_preserves_database_secrets(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime = root / "runtime"
            database = root / "database"
            secret_dir = database / "secrets"

            created = module.prepare(runtime, database)
            self.assertEqual(
                {
                    "postgres-password",
                    "scheduler-token",
                    "ecology-token",
                    "admin-control-token",
                },
                set(created),
            )
            secret_paths = sorted(
                path for path in secret_dir.iterdir() if path.is_file()
            )
            secret_metadata = {
                path.name: (path.stat().st_size, path.stat().st_mode & 0o777)
                for path in secret_paths
            }
            self.assertTrue(all(size > 40 for size, _mode in secret_metadata.values()))
            self.assertTrue(
                all(mode == 0o600 for _size, mode in secret_metadata.values())
            )

            shutil.rmtree(runtime)
            self.assertEqual([], module.prepare(runtime, database))

            self.assertTrue((runtime / "logs").is_dir())
            self.assertEqual(
                secret_metadata,
                {
                    path.name: (path.stat().st_size, path.stat().st_mode & 0o777)
                    for path in sorted(secret_dir.iterdir())
                    if path.is_file()
                },
            )
            self.assertTrue((secret_dir / "admin").is_dir())
            self.assertTrue((secret_dir / "admin-control").is_dir())
            self.assertTrue((database / "shop-assets").is_dir())
            self.assertTrue((database / "backups").is_dir())
            self.assertFalse((runtime / "secrets").exists())

    def test_rejects_symlinked_roots_directories_and_secrets(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime_target = root / "runtime-target"
            database_target = root / "database-target"
            runtime_target.mkdir()
            database_target.mkdir()
            runtime_link = root / "runtime-link"
            runtime_link.symlink_to(runtime_target, target_is_directory=True)
            with self.assertRaises(ValueError):
                module.prepare(runtime_link, root / "database")

            database_link = root / "database-link"
            database_link.symlink_to(database_target, target_is_directory=True)
            with self.assertRaises(ValueError):
                module.prepare(root / "runtime", database_link)

            database = root / "database"
            (database / "secrets").mkdir(parents=True)
            directory_target = root / "external-directory"
            directory_target.mkdir()
            (database / "secrets/admin").symlink_to(
                directory_target, target_is_directory=True
            )
            with self.assertRaises(ValueError):
                module.prepare(root / "runtime", database)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime = root / "runtime"
            database = root / "database"
            secret_dir = database / "secrets"
            secret_dir.mkdir(parents=True)
            target = root / "external-secret"
            target.write_text("sentinel")
            (secret_dir / "postgres-password").symlink_to(target)
            with self.assertRaises(ValueError):
                module.prepare(runtime, database)
            self.assertEqual("sentinel", target.read_text())

    def test_rejects_empty_existing_secret(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = root / "database"
            secret_dir = database / "secrets"
            secret_dir.mkdir(parents=True)
            (secret_dir / "postgres-password").touch()
            with self.assertRaises(ValueError):
                module.prepare(root / "runtime", database)

    def test_cli_defaults_use_runtime_and_database_roots_in_isolated_copy(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            tools = repo / "tools"
            tools.mkdir()
            shutil.copy2(_ROOT / "tools/prepare-local-runtime.py", tools)
            completed = subprocess.run(
                [sys.executable, str(tools / "prepare-local-runtime.py")],
                cwd=repo,
                check=True,
                capture_output=True,
                text=True,
            )

            self.assertTrue((repo / ".runtime/local/logs").is_dir())
            self.assertTrue((repo / ".database/secrets").is_dir())
            self.assertFalse((repo / ".runtime/local/secrets").exists())
            self.assertEqual(
                {
                    "postgres-password",
                    "scheduler-token",
                    "ecology-token",
                    "admin-control-token",
                },
                {
                    path.name
                    for path in (repo / ".database/secrets").iterdir()
                    if path.is_file()
                },
            )
            self.assertIn("New secret files:", completed.stdout)
            self.assertNotIn(".runtime/local/secrets", completed.stdout)

    def test_compose_secret_bind_mounts_resolve_to_database_secrets(self):
        compose = shutil.which("docker")
        if compose is None:
            self.skipTest("Docker Compose is unavailable")
        version = subprocess.run(
            [compose, "compose", "version"], capture_output=True, text=True
        )
        if version.returncode:
            self.skipTest("Docker Compose is unavailable")

        completed = subprocess.run(
            [compose, "compose", "config", "--format", "json"],
            cwd=_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        config = json.loads(completed.stdout)
        mounted_secret_sources = set()
        for service in config["services"].values():
            for volume in service.get("volumes", []):
                target = volume.get("target", "")
                if target == "/run/secrets" or target.startswith("/run/secrets/"):
                    self.assertEqual("bind", volume["type"])
                    source = Path(volume["source"])
                    self.assertTrue(source.is_relative_to(_ROOT / ".database"))
                    mounted_secret_sources.add(source)

        expected = {
            _ROOT / ".database/secrets/postgres-password",
            _ROOT / ".database/secrets/scheduler-token",
            _ROOT / ".database/secrets/ecology-token",
            _ROOT / ".database/secrets/admin-control-token",
            _ROOT / ".database/secrets",
        }
        self.assertTrue(expected.issubset(mounted_secret_sources))


if __name__ == "__main__":
    unittest.main()
