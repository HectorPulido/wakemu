"""Offline installer integrity and standalone Compose contract, no Docker calls."""

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import tarfile
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
                installer.world_services(state), ["wakia", "shop", "world", "ecology"]
            )
            config = state / "world/ai-backend.json"
            config.write_text(json.dumps({"version": 1, "backend": "current"}))
            self.assertEqual(
                installer.world_services(state), ["wakia", "shop", "world", "ecology"]
            )
            config.write_text(json.dumps({"version": 1, "backend": "jondo"}))
            self.assertEqual(
                installer.world_services(state), ["wakia", "shop", "world", "ecology"]
            )
            config.write_text(json.dumps({"version": 1, "backend": "invalid"}))
            with self.assertRaisesRegex(ValueError, "Invalid AI backend configuration"):
                installer.world_services(state)

    def test_world_start_waits_for_selected_services_and_native_ecology(self):
        instance = installer.Installer.__new__(installer.Installer)
        instance.compose = lambda *args: list(args)
        with patch.object(instance, "run") as run:
            instance.start_world_services(["wakia", "shop", "world", "ecology"])
        run.assert_called_once_with(
            "start-world-ai-shop",
            ["up", "-d", "--no-build", "--wait", "wakia", "shop", "world", "ecology"],
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
                "WAKFU_ECOLOGY_IMAGE": "unrelated-ecology:image",
            }
            with patch.dict(os.environ, inherited, clear=True), patch.object(
                installer, "load_public_manifest", return_value=({}, "a" * 64)
            ), patch.object(installer, "source_inventory", return_value=({}, "b" * 64)):
                instance = installer.Installer(args)
            self.assertEqual(instance.env, {"PATH": "/bin"})

    def test_public_artifact_guards_atomic_resume_lock_and_standalone_six_services(
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
            {"postgres", "redis", "world", "ecology", "wakia", "shop"},
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
        world = services.split("  world:", 1)[1].split("  ecology:", 1)[0]
        ecology = services.split("  ecology:", 1)[1].split("  wakia:", 1)[0]
        self.assertIn("WAKFU_ECOLOGY_MODE: external", world)
        self.assertIn("WAKFU_ECOLOGY_URL: http://ecology:8093", world)
        self.assertIn("world: {condition: service_healthy}", ecology)
        self.assertNotIn("ports:", ecology)
        self.assertIn("networks: [isolated]", ecology)
        self.assertIn(
            "${WAKFU_ECOLOGY_IMAGE:?Installer ecology image is required}", ecology
        )
        self.assertIn(
            "dockerfile: rust-services/crates/ecology-service/Dockerfile", ecology
        )
        self.assertIn(
            "test: [CMD, /usr/local/bin/wakemu-ecology, --health-check]", ecology
        )
        self.assertIn(
            "WAKFU_DATABASE_URL: host=postgres dbname=${WAKEMU_INSTALL_DATABASE} user=wakemu",
            ecology,
        )
        self.assertIn("WAKFU_ECOLOGY_TOKEN_FILE: /run/secrets/ecology-token", ecology)
        self.assertIn(
            "${WAKEMU_INSTALL_STATE_DIR}/database/secrets:/run/secrets:ro", ecology
        )

    def test_rust_source_inventory_excludes_generated_cargo_artifacts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "compose.install.yaml").write_text("services: {}\n")
            rust = root / "server/rust-services"
            (rust / "crates/ecology-service/src").mkdir(parents=True)
            (rust / "crates/ecology-service/src/main.rs").write_text("fn main() {}\n")
            (rust / "Cargo.lock").write_text("version = 4\n")
            (rust / "target/release").mkdir(parents=True)
            output = rust / "target/release/wakemu-ecology"
            output.write_bytes(b"first generated binary")
            database = root / "database"
            source_files = {
                ".dockerignore": "*\n!protocol/**\n!seeds/**\n",
                "protocol/catalog.json": "{}\n",
                "data/native-additions.json": "{}\n",
                "seeds/static.sql": "SELECT 1;\n",
                "shop-assets/asset.txt": "public\n",
            }
            for relative, content in source_files.items():
                path = database / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content)
            for relative in (
                "data/installation/catalog.gz",
                "secrets/token",
                "backups/private.sql",
            ):
                path = database / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("not an installer source\n")
            files, original = installer.source_inventory(root)
            self.assertIn("server/rust-services/Cargo.lock", files)
            self.assertIn(
                "server/rust-services/crates/ecology-service/src/main.rs", files
            )
            self.assertFalse(any("/target/" in name for name in files))
            for relative in source_files:
                self.assertIn("database/" + relative, files)
            self.assertFalse(
                any(name.startswith("database/data/installation/") for name in files)
            )
            self.assertFalse(
                any(
                    name.startswith(("database/secrets/", "database/backups/"))
                    for name in files
                )
            )
            output.write_bytes(b"rebuilt generated binary")
            self.assertEqual(installer.source_inventory(root), (files, original))
            archive = root / "sources.tar.gz"
            with tarfile.open(archive, "w:gz") as stream:
                stream.add(root / "server", arcname="server")
                stream.add(database, arcname="database")
                stream.add(
                    root / "compose.install.yaml", arcname="compose.install.yaml"
                )
            self.assertEqual(
                installer.archived_source_inventory(archive), (files, original)
            )
            (database / "seeds/static.sql").write_text("SELECT 2;\n")
            self.assertNotEqual(installer.source_inventory(root)[1], original)
            (database / "seeds/static.sql").write_text(source_files["seeds/static.sql"])
            (database / ".dockerignore").write_text("*\n!seeds/**\n")
            self.assertNotEqual(installer.source_inventory(root)[1], original)
            (database / ".dockerignore").write_text(source_files[".dockerignore"])
            (rust / "Cargo.lock").write_text("version = 4\n# changed dependency lock\n")
            self.assertNotEqual(installer.source_inventory(root)[1], original)

    def test_install_pins_and_builds_native_ecology_before_starting_storage(self):
        class StopBeforeStorage(Exception):
            pass

        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary)
            inputs = state / "inputs"
            inputs.mkdir()
            (state / "world").mkdir()
            digest = hashlib.sha256(b"SELECT 1;\n").hexdigest()
            for name in ("bootstrap.sql", "reviewed.sql"):
                (inputs / name).write_bytes(b"SELECT 1;\n")
            active = "a" * 64
            (inputs / "manifest.json").write_text(
                json.dumps(
                    dict(
                        format="wakemu-installation-seed-v1",
                        contains_private_capture=False,
                        player_tables_exported=[],
                        releases=[dict(revision=active)],
                        active_revision=active,
                        bootstrap_export=dict(
                            path="bootstrap.sql", import_expected_sha256=digest
                        ),
                        reviewed_dungeons=dict(path="reviewed.sql", sha256=digest),
                    )
                )
            )
            instance = installer.Installer.__new__(installer.Installer)
            instance.state = state
            instance.pack = state / "unused-public-pack"
            instance.identity = dict(project="fresh", database="wakemu_fresh")
            instance.progress = dict(installation=instance.identity, stages={})
            instance.source_sha = "b" * 64
            instance.env = {}
            instance.public = dict(
                catalogs=dict(mining_revision=active, fishing_revision=active)
            )
            instance.args = SimpleNamespace(
                project="fresh",
                advertise_host="127.0.0.1",
                world_port=15556,
                dispatcher_port=15558,
                http_port=18081,
                shop_port=18083,
            )
            calls = []

            def run(key, command, **kwargs):
                calls.append((key, command))
                if key == "start-storage":
                    raise StopBeforeStorage()

            instance.run = run
            original_run_path = installer.runpy.run_path

            def load_helper(path):
                if str(path).endswith("prepare-local-runtime.py"):
                    return dict(
                        prepare=lambda *args: None,
                        configure_service_user=lambda *args: None,
                    )
                return original_run_path(path)

            with patch.object(
                installer.subprocess, "check_output", return_value=""
            ), patch.object(installer.runpy, "run_path", side_effect=load_helper):
                with self.assertRaises(StopBeforeStorage):
                    instance._install()
            stages = [key for key, command in calls]
            self.assertEqual(
                stages[-5:],
                [
                    "build-world",
                    "build-wakia",
                    "build-shop",
                    "build-ecology",
                    "start-storage",
                ],
            )
            ecology_command = next(
                command for key, command in calls if key == "build-ecology"
            )
            self.assertEqual(ecology_command[-2:], ["build", "ecology"])
            environment = (state / "compose.env").read_text()
            self.assertIn(
                "WAKFU_ECOLOGY_IMAGE=wakemu-install-ecology:" + "b" * 16 + "\n",
                environment,
            )
            self.assertEqual(
                stat.S_IMODE((state / "compose.env").stat().st_mode), 0o600
            )

    def test_source_recovery_rebuilds_ecology_without_fabricating_prior_completion(
        self,
    ):
        for previously_built in (False, True):
            with self.subTest(
                previously_built=previously_built
            ), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                (root / "tools").mkdir()
                source = root / "tools/install-wakemu.py"
                source.write_bytes(b"old installer source")
                archive = root / "prior.tar.gz"
                with tarfile.open(archive, "w:gz") as stream:
                    stream.add(source, arcname="tools/install-wakemu.py")
                _, old_sha = installer.archived_source_inventory(archive)
                state = root / "state"
                inputs = state / "inputs"
                (state / "receipts").mkdir(parents=True)
                inputs.mkdir()
                pack = root / "pack"
                pack.mkdir()
                releases = [dict(revision="a" * 64)]

                def artifact(base, name, data):
                    (base / name).write_bytes(data)
                    return dict(path=name, sha256=hashlib.sha256(data).hexdigest())

                bootstrap = artifact(inputs, "bootstrap.sql", b"original bootstrap")
                bootstrap["import_expected_sha256"] = bootstrap["sha256"]
                reviewed = artifact(inputs, "reviewed.sql", b"original reviewed")
                catalog = artifact(
                    pack, "catalog.json", json.dumps(dict(releases=releases)).encode()
                )
                (inputs / "manifest.json").write_text(
                    json.dumps(
                        dict(
                            format="wakemu-installation-seed-v1",
                            contains_private_capture=False,
                            player_tables_exported=[],
                            releases=releases,
                            active_revision="a" * 64,
                            bootstrap_export=bootstrap,
                            reviewed_dungeons=reviewed,
                        )
                    )
                )
                identity = dict(
                    project="fresh",
                    database="wakemu_fresh",
                    manifest_sha256="c" * 64,
                    source_inventory_sha256="b" * 64,
                )
                prior = dict(identity, source_inventory_sha256=old_sha)
                stages = {
                    key: dict(command=[key], completed_at="original")
                    for key in (
                        "compose-config",
                        "build-world",
                        "build-wakia",
                        "build-shop",
                        "bootstrap",
                    )
                }
                if previously_built:
                    stages["build-ecology"] = dict(
                        command=["original ecology build"], completed_at="original"
                    )
                instance = installer.Installer.__new__(installer.Installer)
                instance.args = SimpleNamespace(resume_source_archive=archive)
                instance.state, instance.pack = state, pack
                instance.public = dict(
                    catalogs=dict(manifest="catalog", active_revision="a" * 64),
                    artifacts=dict(catalog=catalog),
                    bootstrap=dict(sha256=bootstrap["sha256"]),
                    reviewed_dungeons=dict(sha256=reviewed["sha256"]),
                )
                instance.source_files = {
                    "tools/install-wakemu.py": hashlib.sha256(
                        b"new installer source"
                    ).hexdigest()
                }
                instance.source_sha, instance.identity = "b" * 64, identity
                instance.progress = dict(installation=prior, stages=dict(stages))
                instance.resume_source()
                audit = json.loads(
                    (
                        state
                        / "receipts"
                        / instance.progress["source_updates"][0]["receipt"]
                    ).read_text()
                )
                self.assertEqual(audit["previous_stages"], stages)
                self.assertEqual(
                    "ecology" in audit["previous_images"], previously_built
                )
                self.assertEqual(
                    "build-ecology" in audit["invalidated_stages"], previously_built
                )
                self.assertEqual(
                    audit["next_images"]["ecology"],
                    "wakemu-install-ecology:" + "b" * 16,
                )
                self.assertNotIn("build-ecology", instance.progress["stages"])
                self.assertEqual(
                    instance.progress["stages"]["bootstrap"], stages["bootstrap"]
                )
