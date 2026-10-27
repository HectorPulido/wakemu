"""Explicit pre-World source recovery preserves immutable completed data."""
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import tarfile
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location(
    "owned_source_resume", Path(__file__).resolve().parents[1] / "install-wakemu.py"
)
installer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(installer)


class InstallerSourceResumeTests(unittest.TestCase):
    def test_prior_archive_data_identity_rebuild_audit_negative_guards_and_crash_recovery(
        self,
    ):
        def write_json(path, value):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(value))

        def fixture(root):
            old = {
                "tools/install-wakemu.py": b"old installer",
                "server/tools/install_environmental_profiles.py": b"old verifier",
                "server/migrations/001_original.sql": b"stable migration",
                "server/tools/import_native_catalogs.py": b"stable importer",
                "compose.install.yaml": b"stable compose",
            }
            for name, data in old.items():
                p = root / name
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(data)
            archive = root / "original.tar.gz"
            with tarfile.open(archive, "w:gz") as tar:
                for name in old:
                    tar.add(root / name, arcname=name)
            _, old_sha = installer.source_inventory(root)
            for name in (
                "tools/install-wakemu.py",
                "server/tools/install_environmental_profiles.py",
            ):
                (root / name).write_bytes(b"new reviewed tool")
            test = root / "tools/tests/added.py"
            test.parent.mkdir()
            test.write_text("# test only")
            files, new_sha = installer.source_inventory(root)
            state = root / "state"
            pack = root / "pack"
            inputs = state / "inputs"
            (state / "receipts").mkdir(parents=True)
            pack.mkdir()
            inputs.mkdir()

            def artifact(base, name, data):
                p = base / name
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(data)
                return dict(path=name, sha256=hashlib.sha256(data).hexdigest())

            bootstrap = artifact(inputs, "bootstrap.jsonl", b"original bootstrap")
            bootstrap["import_expected_sha256"] = bootstrap["sha256"]
            reviewed = artifact(inputs, "reviewed.sql", b"original reviewed")
            seed = artifact(inputs, "seed.sql", b"original seed")
            public_seed = artifact(pack, "public-seed.sql", b"original seed")
            releases = [
                dict(
                    revision="a" * 64,
                    documents=[dict(path="original.json", sha256="b" * 64)],
                )
            ]
            catalog = artifact(
                pack, "catalog.json", json.dumps(dict(releases=releases)).encode()
            )
            public = dict(
                catalogs=dict(manifest="catalog", active_revision="a" * 64),
                artifacts=dict(catalog=catalog, seed=public_seed),
                sql_seeds=["seed"],
                bootstrap=dict(sha256=bootstrap["sha256"]),
                reviewed_dungeons=dict(sha256=reviewed["sha256"]),
            )
            write_json(
                inputs / "manifest.json",
                dict(
                    format="wakemu-installation-seed-v1",
                    contains_private_capture=False,
                    player_tables_exported=[],
                    releases=releases,
                    active_revision="a" * 64,
                    bootstrap_export=bootstrap,
                    reviewed_dungeons=reviewed,
                    additional_seeds=[seed],
                ),
            )
            identity = dict(
                project="test",
                database="wakemu_test",
                manifest_sha256="c" * 64,
                source_inventory_sha256=new_sha,
            )
            prior = dict(identity, source_inventory_sha256=old_sha)
            progress = dict(
                installation=prior,
                stages={
                    key: dict(command=[key, "original"], completed_at="original")
                    for key in (
                        "materialize-public-data",
                        "compose-config",
                        "build-world",
                        "build-ai",
                        "build-shop",
                        "migrate-schema",
                        "catalog-" + "a" * 64,
                        "bootstrap",
                        "reviewed-dungeons",
                        "public-seed-0",
                    )
                },
            )
            installer.atomic_json(state / "installation.json", progress)
            obj = installer.Installer.__new__(installer.Installer)
            obj.args = SimpleNamespace(resume_source_archive=archive)
            obj.state, obj.pack, obj.public = state, pack, public
            obj.source_files, obj.source_sha, obj.identity, obj.progress = (
                files,
                new_sha,
                identity,
                deepcopy(progress),
            )
            return obj

        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            for kind in (
                "no-flag",
                "identity",
                "prior-proof",
                "attempted-world",
                "completed",
                "seed-tamper",
                "catalog-tamper",
                "migration",
                "completed-consumer",
            ):
                obj = fixture(base / kind)
                if kind == "no-flag":
                    obj.args.resume_source_archive = None
                elif kind == "identity":
                    obj.identity = dict(obj.identity, manifest_sha256="d" * 64)
                elif kind == "prior-proof":
                    obj.progress["installation"]["source_inventory_sha256"] = "d" * 64
                elif kind == "attempted-world":
                    (obj.state / "receipts/start-world-ai-shop.log").write_text(
                        "previous failed launch"
                    )
                elif kind == "completed":
                    obj.progress["status"] = "VERIFIED"
                elif kind == "seed-tamper":
                    (obj.state / "inputs/seed.sql").write_bytes(b"changed")
                elif kind == "catalog-tamper":
                    p = obj.state / "inputs/manifest.json"
                    v = json.loads(p.read_text())
                    v["releases"] = []
                    write_json(p, v)
                elif kind == "migration":
                    obj.source_files = {
                        **obj.source_files,
                        "server/migrations/002_new.sql": "e" * 64,
                    }
                elif kind == "completed-consumer":
                    obj.progress["stages"]["environmental-profiles"] = dict(
                        command=["original"]
                    )
                with self.subTest(kind=kind), self.assertRaises(ValueError):
                    obj.resume_source()
                self.assertFalse(list((obj.state / "receipts").glob("source-update-*")))
            obj = fixture(base / "positive")
            old = deepcopy(obj.progress)
            obj.resume_source()
            self.assertEqual(obj.progress["installation"], obj.identity)
            for key in (
                "materialize-public-data",
                "migrate-schema",
                "catalog-" + "a" * 64,
                "bootstrap",
                "reviewed-dungeons",
                "public-seed-0",
            ):
                self.assertEqual(obj.progress["stages"][key], old["stages"][key])
            for key in ("compose-config", "build-world", "build-ai", "build-shop"):
                self.assertNotIn(key, obj.progress["stages"])
            receipt = (
                obj.state / "receipts" / obj.progress["source_updates"][0]["receipt"]
            )
            audit = json.loads(receipt.read_text())
            self.assertEqual(audit["previous_stages"], old["stages"])
            self.assertNotEqual(audit["previous_images"], audit["next_images"])
            with patch.object(
                installer.subprocess,
                "Popen",
                side_effect=AssertionError("cached data reexecuted"),
            ):
                obj.run("bootstrap", old["stages"]["bootstrap"]["command"])
                with self.assertRaisesRegex(ValueError, "command differs"):
                    obj.run("bootstrap", ["changed"])
            # The exact audit can be committed after a crash between its write
            # and the installation-progress replacement, without a second transition.
            obj = fixture(base / "crash")
            original_atomic = installer.atomic_json

            def fail_progress(path, value):
                if Path(path).name == "installation.json":
                    raise RuntimeError("crash before progress")
                original_atomic(path, value)

            with patch.object(installer, "atomic_json", side_effect=fail_progress):
                with self.assertRaisesRegex(RuntimeError, "crash before progress"):
                    obj.resume_source()
            obj.progress = json.loads((obj.state / "installation.json").read_text())
            obj.resume_source()
            self.assertEqual(len(obj.progress["source_updates"]), 1)
            self.assertEqual(
                len(list((obj.state / "receipts").glob("source-update-*"))), 1
            )
