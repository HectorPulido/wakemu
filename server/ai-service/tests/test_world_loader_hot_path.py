"""Hot-path optimizations preserve byte-versioned SDK loading semantics."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import os
from pathlib import Path
import sys
import tempfile
import unittest

_HERE = Path(__file__).resolve().parents[1]
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from world_loader import load_entry


class WorldLoaderHotPathTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        (self.directory / "world_entry.py").write_text(
            "def run_npc_turn():\n    return 'original'\n"
        )

    def legacy_version(self):
        checksum = hashlib.sha256()
        for path in sorted(self.directory.rglob("*.py")):
            name, data = (
                path.relative_to(self.directory).as_posix().encode(),
                path.read_bytes(),
            )
            checksum.update(len(name).to_bytes(8, "big"))
            checksum.update(name)
            checksum.update(len(data).to_bytes(8, "big"))
            checksum.update(data)
        return "_wakfu_native_ai_sdk_" + checksum.hexdigest()

    def test_missing_directory_retains_complete_sdk_error(self):
        with self.assertRaisesRegex(
            ValueError, "Complete native AI SDK is unavailable"
        ):
            load_entry(self.directory / "missing")

    def test_component_sorting_hidden_files_and_symlinks_preserve_legacy_digest(self):
        for name in ("a/z.py", "a.py", ".hidden/nested.py", "future/tree/new.py"):
            path = self.directory / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("VALUE = 1\n")
        (self.directory / "alias.py").symlink_to("a.py")
        (self.directory / "directory_alias").symlink_to(
            "future", target_is_directory=True
        )
        self.assertEqual(
            load_entry(self.directory).__module__.split(".")[0], self.legacy_version()
        )

    def test_warm_entry_detects_same_size_restored_mtime_and_can_roll_back(self):
        path = self.directory / "world_entry.py"
        original, metadata = path.read_bytes(), path.stat()
        old = load_entry(self.directory)
        path.write_bytes(original.replace(b"original", b"modified"))
        os.utime(path, ns=(metadata.st_atime_ns, metadata.st_mtime_ns))
        new = load_entry(self.directory)
        self.assertEqual((old(), new()), ("original", "modified"))
        self.assertNotEqual(old.__module__, new.__module__)
        path.write_bytes(original)
        self.assertIs(load_entry(self.directory), old)

    def test_new_nested_sources_change_version_and_lazy_import_remains_frozen(self):
        old = load_entry(self.directory)
        source = self.directory / "future" / "deep" / "effect.py"
        source.parent.mkdir(parents=True)
        source.write_text("VALUE = 'snapshot'\n")
        (self.directory / "world_entry.py").write_text(
            "def run_npc_turn():\n    from .future.deep.effect import VALUE\n    return VALUE\n"
        )
        new = load_entry(self.directory)
        source.write_text("VALUE = 'subsequent'\n")
        self.assertNotEqual(new.__module__, old.__module__)
        self.assertEqual(new(), "snapshot")
        self.assertEqual(load_entry(self.directory)(), "subsequent")
        source.unlink()
        self.assertEqual(
            load_entry(self.directory).__module__.split(".")[0], self.legacy_version()
        )

    def test_concurrent_loads_share_entry_and_failed_revision_preserves_old_entry(self):
        with ThreadPoolExecutor(max_workers=8) as executor:
            entries = list(
                executor.map(lambda _: load_entry(self.directory), range(32))
            )
        self.assertTrue(all(entry is entries[0] for entry in entries))
        path = self.directory / "world_entry.py"
        original = path.read_bytes()
        path.write_text("raise RuntimeError('broken hot revision')\n")
        broken_package = self.legacy_version()
        with self.assertRaisesRegex(RuntimeError, "broken hot revision"):
            load_entry(self.directory)
        self.assertFalse(
            any(
                name == broken_package or name.startswith(broken_package + ".")
                for name in sys.modules
            )
        )
        self.assertEqual(entries[0](), "original")
        path.write_bytes(original)
        self.assertIs(load_entry(self.directory), entries[0])


if __name__ == "__main__":
    unittest.main()
