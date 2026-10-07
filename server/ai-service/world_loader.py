"""Load versioned AI SDK code from a directory through one stable world hook.

World needs only this file's load_entry(directory) interface. New Python
modules automatically participate in the version; no world import lists or
spell-specific handlers must be edited when the SDK evolves.
"""
import hashlib
import importlib
import importlib.abc
import importlib.util
from pathlib import Path
import sys
import threading
import types

_LOCK = threading.RLock()


class _SnapshotLoader(importlib.abc.Loader):
    def __init__(self, source, filename):
        self.source, self.filename = source, filename

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        # Compile the exact bytes that established the SDK version. Timestamp
        # based pyc caches cannot safely distinguish same-size rapid edits.
        exec(compile(self.source, self.filename, "exec"), module.__dict__)


class _SnapshotFinder(importlib.abc.MetaPathFinder):
    def __init__(self):
        self.versions = {}

    def find_spec(self, fullname, path=None, target=None):
        package, _, suffix = fullname.partition(".")
        version = self.versions.get(package)
        if version is None or not suffix:
            return None
        directory, sources = version
        relative = suffix.replace(".", "/")
        package_file, module_file = relative + "/__init__.py", relative + ".py"
        name = package_file if package_file in sources else module_file
        if name not in sources:
            if any(name.startswith(relative + "/") for name in sources):
                spec = importlib.machinery.ModuleSpec(
                    fullname, loader=None, is_package=True
                )
                spec.submodule_search_locations = [str(directory / relative)]
                return spec
            return None
        filename = str(directory / name)
        return importlib.util.spec_from_file_location(
            fullname,
            filename,
            loader=_SnapshotLoader(sources[name], filename),
            submodule_search_locations=[str(directory / relative)]
            if name == package_file
            else None,
        )


_FINDER = _SnapshotFinder()


def load_entry(directory):
    directory = Path(directory).resolve()
    files = sorted(directory.rglob("*.py"))
    if not files or not (directory / "world_entry.py").is_file():
        raise ValueError("Complete native AI SDK is unavailable")
    checksum, sources = hashlib.sha256(), {}
    for path in files:
        relative = path.relative_to(directory).as_posix().encode()
        data = path.read_bytes()
        sources[path.relative_to(directory).as_posix()] = data
        checksum.update(len(relative).to_bytes(8, "big"))
        checksum.update(relative)
        checksum.update(len(data).to_bytes(8, "big"))
        checksum.update(data)
    package = "_wakfu_native_ai_sdk_" + checksum.hexdigest()
    with _LOCK:
        if package not in sys.modules:
            if _FINDER not in sys.meta_path:
                sys.meta_path.insert(0, _FINDER)
            _FINDER.versions[package] = directory, sources
            root = types.ModuleType(package)
            root.__path__ = [str(directory)]
            root.__package__ = package
            sys.modules[package] = root
        try:
            return importlib.import_module(package + ".world_entry").run_npc_turn
        except Exception:
            for name in list(sys.modules):
                if name == package or name.startswith(package + "."):
                    sys.modules.pop(name, None)
            _FINDER.versions.pop(package, None)
            raise
