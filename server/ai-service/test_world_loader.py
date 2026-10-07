"""Stable world-loader tests for private, complete SDK package versions."""
from pathlib import Path
import sys
import tempfile
import unittest
import os
import py_compile

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from world_loader import load_entry


class WorldLoaderTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.before_path = list(sys.path)

    def sdk(self, name):
        directory = Path(self.temporary.name) / name
        directory.mkdir()
        (directory / "world_entry.py").write_text(
            "from .features.current import value\n"
            "def run_npc_turn(*args, **kwargs):\n"
            "    return value()\n"
        )
        (directory / "features").mkdir()
        (directory / "features" / "__init__.py").write_text("")
        (directory / "features" / "current.py").write_text(
            "def value():\n    return 'initial'\n"
        )
        return directory

    def private_modules(self, entry):
        package = entry.__module__.split(".", 1)[0]
        return package, {
            name
            for name in sys.modules
            if name == package or name.startswith(package + ".")
        }

    def test_hot_reload_creates_new_private_version_without_mutating_old_entry(self):
        directory = self.sdk("reload")
        old_entry = load_entry(directory)
        old_package, old_modules = self.private_modules(old_entry)
        self.assertEqual(old_entry(), "initial")
        (directory / "features" / "current.py").write_text(
            "def value():\n    return 'reloaded'\n"
        )

        new_entry = load_entry(directory)
        new_package, new_modules = self.private_modules(new_entry)

        self.assertNotEqual(old_package, new_package)
        self.assertEqual(old_entry(), "initial")
        self.assertEqual(new_entry(), "reloaded")
        self.assertTrue(old_modules <= set(sys.modules))
        self.assertTrue(new_modules <= set(sys.modules))
        self.assertEqual(sys.path, self.before_path)

    def test_two_sdk_directories_with_same_module_names_are_isolated(self):
        first_dir = self.sdk("first")
        second_dir = self.sdk("second")
        (first_dir / "features" / "current.py").write_text(
            "def value():\n    return 'first-directory'\n"
        )
        (second_dir / "features" / "current.py").write_text(
            "def value():\n    return 'second-directory'\n"
        )

        first = load_entry(first_dir)
        second = load_entry(second_dir)

        first_package, _ = self.private_modules(first)
        second_package, _ = self.private_modules(second)
        self.assertNotEqual(first_package, second_package)
        self.assertEqual(first(), "first-directory")
        self.assertEqual(second(), "second-directory")
        self.assertEqual(sys.path, self.before_path)

    def test_same_size_same_timestamp_edit_does_not_reuse_stale_bytecode(self):
        directory = self.sdk("same-size")
        source = directory / "features" / "current.py"
        source.write_text("def value():\n    return 'before'\n")
        stat = source.stat()
        py_compile.compile(str(source), doraise=True)
        old_entry = load_entry(directory)
        source.write_text("def value():\n    return 'after!'\n")
        os.utime(source, ns=(stat.st_atime_ns, stat.st_mtime_ns))
        self.assertEqual(source.stat().st_size, stat.st_size)
        new_entry = load_entry(directory)
        self.assertEqual(old_entry(), "before")
        self.assertEqual(new_entry(), "after!")
        self.assertNotEqual(old_entry.__module__, new_entry.__module__)

    def test_lazy_future_namespace_module_uses_the_frozen_version_bytes(self):
        directory = self.sdk("lazy-namespace")
        (directory / "future").mkdir()
        source = directory / "future" / "ability.py"
        source.write_text("value = 'owned-original'\n")
        (directory / "world_entry.py").write_text(
            "def run_npc_turn(*args, **kwargs):\n"
            "    from .future.ability import value\n"
            "    return value\n"
        )
        entry = load_entry(directory)
        source.write_text("value = 'changed-after-versioning'\n")
        self.assertEqual(entry(), "owned-original")
        self.assertEqual(load_entry(directory)(), "changed-after-versioning")

    def test_missing_sdk_and_missing_entry_are_rejected_without_path_changes(self):
        empty = Path(self.temporary.name) / "empty"
        empty.mkdir()
        entryless = Path(self.temporary.name) / "entryless"
        entryless.mkdir()
        (entryless / "support.py").write_text("VALUE = 1\n")

        for path in (empty, entryless):
            with self.subTest(path=path), self.assertRaisesRegex(
                ValueError, "Complete native AI SDK is unavailable"
            ):
                load_entry(path)
        self.assertEqual(sys.path, self.before_path)

    def test_import_failure_cleans_partial_package_and_fixed_sdk_can_retry(self):
        directory = Path(self.temporary.name) / "broken"
        directory.mkdir()
        (directory / "world_entry.py").write_text(
            "from .feature import value\n"
            "def run_npc_turn(*args, **kwargs):\n    return value\n"
        )
        (directory / "feature.py").write_text("raise RuntimeError('broken SDK')\n")
        before_private = {
            name for name in sys.modules if name.startswith("_wakfu_native_ai_sdk_")
        }
        with self.assertRaisesRegex(RuntimeError, "broken SDK"):
            load_entry(directory)
        after_private = {
            name for name in sys.modules if name.startswith("_wakfu_native_ai_sdk_")
        }
        self.assertEqual(after_private, before_private)

        (directory / "feature.py").write_text("value = 'fixed'\n")
        entry = load_entry(directory)
        self.assertEqual(entry(), "fixed")
        self.assertEqual(sys.path, self.before_path)

    def test_actual_ai_service_sdk_loads_through_private_relative_package(self):
        directory = _HERE
        entry = load_entry(directory)
        package, loaded = self.private_modules(entry)
        self.assertEqual(entry.__name__, "run_npc_turn")
        self.assertTrue(entry.__module__.startswith(package + ".world_entry"))
        self.assertIn(package + ".world_bridge", loaded)
        self.assertIn(package + ".native_oracle", loaded)
        self.assertIn(package + ".native_turn", loaded)
        self.assertEqual(sys.path, self.before_path)


if __name__ == "__main__":
    unittest.main()
