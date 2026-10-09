import importlib.util
from pathlib import Path
import tempfile
import unittest
import zipfile

_SPEC = importlib.util.spec_from_file_location(
    "empty_particle_patch",
    Path(__file__).resolve().parents[2]
    / "client-tools/patches/patch-empty-particle-ids.py",
)
patch = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(patch)


class EmptyParticleIdPatchTests(unittest.TestCase):
    def test_only_empty_sentinel_guard_changes_and_repeat_preserves_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "scripts.jar"
            original = b"function aps()\r\n  " + patch.ORIGINAL + b"\r\nend\r\n"
            with zipfile.ZipFile(archive, "w") as target:
                target.writestr(patch.MEMBER, original)
                target.writestr("other.lua", b"unchanged")
            original_archive = archive.read_bytes()
            backup = Path(directory) / "backups/original.jar"
            self.assertTrue(patch.patch_archive(archive, backup))
            with zipfile.ZipFile(archive) as target:
                self.assertEqual(
                    target.read(patch.MEMBER),
                    original.replace(patch.ORIGINAL, patch.PATCHED),
                )
                self.assertEqual(target.read("other.lua"), b"unchanged")
            self.assertFalse(patch.patch_archive(archive, backup))
            self.assertEqual(
                backup.read_bytes(),
                original_archive,
            )

    def test_unknown_native_guard_rejects_without_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "scripts.jar"
            with zipfile.ZipFile(archive, "w") as target:
                target.writestr(patch.MEMBER, b"unknown source")
            original = archive.read_bytes()
            with self.assertRaises(ValueError):
                patch.patch_archive(archive)
            self.assertEqual(archive.read_bytes(), original)
