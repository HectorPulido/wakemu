"""Offline installer integrity and standalone Compose contract, no Docker calls."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "owned_install_wakemu", ROOT / "tools/install-wakemu.py"
)
installer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(installer)


class InstallWakemuTests(unittest.TestCase):
    def test_install_starts_only_selected_planner_for_world(self):
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary)
            (state / "world").mkdir()
            self.assertEqual(
                installer.world_services(state), ["wakia", "shop", "world"]
            )
            config = state / "world/ai-backend.json"
            config.write_text(json.dumps({"version": 1, "backend": "current"}))
            self.assertEqual(
                installer.world_services(state), ["wakia", "shop", "world"]
            )
            config.write_text(json.dumps({"version": 1, "backend": "jondo"}))
            self.assertEqual(
                installer.world_services(state), ["wakia", "shop", "world"]
            )
            config.write_text(json.dumps({"version": 1, "backend": "invalid"}))
            with self.assertRaisesRegex(ValueError, "Invalid AI backend configuration"):
                installer.world_services(state)

    def test_wakia_is_ready_before_world_starts(self):
        instance = installer.Installer.__new__(installer.Installer)
        instance.compose = lambda *args: list(args)
        with patch.object(instance, "run") as run:
            instance.start_world_services(["wakia", "shop", "world"])
        run.assert_called_once_with(
            "start-world-ai-shop",
            ["up", "-d", "--no-build", "--wait", "wakia", "shop", "world"],
            repeat=True,
        )

    def test_install_ignores_inherited_wakia_image_override(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            args = SimpleNamespace(
                project="fresh", data_pack=root / "pack", state_dir=root / "state"
            )
            inherited = {
                "PATH": "/bin",
                "WAKIA_IMAGE": "unrelated:image",
                "WAKFU_AI_IMAGE": "other:image",
            }
            with patch.dict(os.environ, inherited, clear=True), patch.object(
                installer, "load_public_manifest", return_value=({}, "a" * 64)
            ), patch.object(installer, "source_inventory", return_value=({}, "b" * 64)):
                instance = installer.Installer(args)
            self.assertEqual(instance.env, {"PATH": "/bin"})

    def test_public_artifact_guards_atomic_resume_lock_and_standalone_five_services(
        self,
    ):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "server/migrations").mkdir(parents=True)
            artifact = root / "public.sql"
            artifact.write_bytes(b"SELECT 1;\n")
            row = {
                "path": "public.sql",
                "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
            }
            self.assertEqual(installer.verified_artifact(root, row), artifact)
            for invalid in (
                "../public.sql",
                "/public.sql",
                "a/../public.sql",
                "a\\public.sql",
                "./public.sql",
                "a//public.sql",
            ):
                with self.subTest(path=invalid), self.assertRaises(ValueError):
                    installer.safe_child(root, invalid)
            (root / "alias.sql").symlink_to(artifact)
            with self.assertRaises(ValueError):
                installer.safe_child(root, "alias.sql")
            artifact.write_bytes(b"SELECT 2;\n")
            with self.assertRaisesRegex(ValueError, "digest mismatch"):
                installer.verified_artifact(root, row)
            (root / "manifest.json").write_text(
                json.dumps({"format": installer.FORMAT})
            )
            with self.assertRaises(ValueError):
                installer.load_public_manifest(root)
            (root / "manifest.json").write_text(
                json.dumps(
                    {"format": installer.FORMAT, "contains_private_capture": True}
                )
            )
            with self.assertRaisesRegex(ValueError, "Private installation"):
                installer.load_public_manifest(root)
            (root / "manifest.json").write_text(
                json.dumps(
                    {
                        "format": installer.FORMAT,
                        "contains_private_capture": False,
                        "player_tables_exported": [],
                    }
                )
            )
            manifest, digest = installer.load_public_manifest(root)
            self.assertEqual(manifest["format"], installer.FORMAT)
            self.assertEqual(
                digest,
                hashlib.sha256((root / "manifest.json").read_bytes()).hexdigest(),
            )
            with self.assertRaises(ValueError):
                installer.migrations(root)
            (root / "server/migrations/001_one.sql").write_text("SELECT 1;\n")
            (root / "server/migrations/002_two.sql").write_text("SELECT 2;\n")
            self.assertEqual(
                [r["version"] for r in installer.migrations(root)], ["001", "002"]
            )
            (root / "server/migrations/004_gap.sql").write_text("SELECT 4;\n")
            with self.assertRaisesRegex(ValueError, "contiguous"):
                installer.migrations(root)
            receipt = root / "receipt.json"
            installer.atomic_json(
                receipt, {"status": "complete", "source": "immutable"}
            )
            self.assertEqual(stat.S_IMODE(receipt.stat().st_mode), 0o600)
            self.assertEqual(
                json.loads(receipt.read_text()),
                {"status": "complete", "source": "immutable"},
            )
            with installer.installation_lock(root):
                with self.assertRaisesRegex(ValueError, "Another installer"):
                    with installer.installation_lock(root):
                        self.fail("Concurrent installer acquired the same state")
            with installer.installation_lock(root):
                pass
        compose = (ROOT / "compose.install.yaml").read_text()
        services = compose.split("\nvolumes:", 1)[0].split("\nnetworks:", 1)[0]
        self.assertEqual(
            set(re.findall(r"^  ([a-z][a-z0-9_-]*):\s*$", services, re.M)),
            {"postgres", "redis", "world", "ai", "wakia", "shop"},
        )
        self.assertNotIn("restore", compose.lower())
        self.assertNotIn("external: true", compose)
        self.assertIn("wakia: {condition: service_healthy}", compose)
        self.assertIn("aliases: [ai-jondo]", compose)
        self.assertIn("./database/shop-assets:/shop-assets:ro", compose)
        self.assertRegex(
            compose, r"(?m)^\s+- 127\.0\.0\.1:\$\{WAKEMU_INSTALL_SHOP_PORT[^\n]+:18083$"
        )
        postgres = services.split("  postgres:", 1)[1].split("  redis:", 1)[0]
        self.assertNotIn("ports:", postgres)
        self.assertNotRegex(compose, r"(?m)^\s+- .*client(?:/|:)")

    def test_reviewed_dungeon_import_contract_and_failure_propagation(self):
        import sys

        source = installer.REVIEWED_DUNGEON_IMPORT
        class FakePath:
            def __init__(self, value):
                self.value = str(value)

            def read_text(self):
                return "password"

            def read_bytes(self):
                return b"reviewed seed"

            def write_text(self, value):
                written[self.value] = value

        class FakeDatabase:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def execute(self, statement, **kwargs):
                executed.append((statement, kwargs))
                if execute_error:
                    raise execute_error

        class FakePsycopg:
            class rows:
                dict_row = object()

            @staticmethod
            def connect(*args, **kwargs):
                connections.append((args, kwargs))
                return db

        database_module = __import__("tools.build_clean_database_backup", fromlist=["*"])
        exporter_module = __import__("tools.export_installation_seed", fromlist=["*"])
        scenarios = (
            (None, None, None),
            (ValueError("paired dungeon pins disagree"), None, None),
            (None, ValueError("immutable dungeon content conflict"), None),
            (None, None, ValueError("immutable reviewed configuration changed")),
        )
        for merge_error, execute_error, verify_error in scenarios:
            succeeds = not any((merge_error, execute_error, verify_error))
            with self.subTest(merge_error=merge_error, verify_error=verify_error):
                connections, executed, written = [], [], {}
                db = FakeDatabase()

                def merge(connection, data):
                    self.assertIs(connection, db)
                    self.assertEqual(data, b"reviewed seed")
                    if merge_error:
                        raise merge_error
                    return "MERGED SQL", [{"route_key": "r", "previous": 1, "public": 2, "selected": 2}]

                def verify(connection):
                    self.assertIs(connection, db)
                    if verify_error:
                        raise verify_error

                fake_psycopg = FakePsycopg
                with patch.dict(os.environ, {
                    "WAKFU_DATABASE_PASSWORD_FILE": "/password",
                    "WAKFU_DATABASE_URL": "dbname=wakemu_test",
                }), patch.object(sys, "argv", ["installer", "/reviewed.sql"]), patch.dict(
                    sys.modules,
                    {"psycopg": fake_psycopg, "psycopg.rows": fake_psycopg.rows},
                ), patch.object(database_module, "merge_public_dungeon_pins", side_effect=merge), patch.object(
                    exporter_module, "reviewed_dungeon_rows", side_effect=verify
                ), patch("pathlib.Path", FakePath):
                    if succeeds:
                        exec(source, {"__name__": "__main__"})
                    else:
                        with self.assertRaises(ValueError):
                            exec(source, {"__name__": "__main__"})
                self.assertEqual(connections[0][1]["autocommit"], True)
                self.assertIs(connections[0][1]["row_factory"], fake_psycopg.rows.dict_row)
                if succeeds:
                    self.assertEqual(executed, [("MERGED SQL", {"prepare": False})])
                    self.assertEqual(
                        json.loads(written["/installation-receipts/reviewed-dungeon-pins.json"]),
                        [{"route_key": "r", "previous": 1, "public": 2, "selected": 2}],
                    )
                else:
                    self.assertNotIn("/installation-receipts/reviewed-dungeon-pins.json", written)
