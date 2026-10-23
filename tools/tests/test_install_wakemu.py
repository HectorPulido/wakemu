"""Offline installer integrity and standalone Compose contract, no Docker calls."""
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import stat
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "owned_install_wakemu", ROOT / "tools/install-wakemu.py"
)
installer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(installer)


class InstallWakemuTests(unittest.TestCase):
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
            {"postgres", "redis", "world", "ai", "shop"},
        )
        self.assertNotIn("restore", compose.lower())
        self.assertNotIn("external: true", compose)
        self.assertIn("./database/shop-assets:/shop-assets:ro", compose)
        self.assertRegex(
            compose, r"(?m)^\s+- 127\.0\.0\.1:\$\{WAKEMU_INSTALL_SHOP_PORT[^\n]+:18083$"
        )
        postgres = services.split("  postgres:", 1)[1].split("  redis:", 1)[0]
        self.assertNotIn("ports:", postgres)
        self.assertNotRegex(compose, r"(?m)^\s+- .*client(?:/|:)")
