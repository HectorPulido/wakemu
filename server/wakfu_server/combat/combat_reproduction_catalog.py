"""Pinned native-catalog capture and strictly offline replay.

Enter capture before engine initialization. Enter replay in a fresh subprocess
before importing modules that build indexes at import time. Patching aliases
cannot undo already materialized indexes or lru_cache values.
"""
from contextlib import contextmanager
import importlib
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import sys

from wakfu_server import native_catalog

VERSION = 1
MAX_DOCUMENT_BYTES = 1_000_000_000
MAX_MANIFEST_BYTES = 32 * 1024 * 1024
MAX_TOTAL_BYTES = 4_000_000_000
_ACTIVE_CATALOG_DUPLICATES = []

FUNCTIONS = (
    "load",
    "read_bytes",
    "read_text",
    "open",
    "exists",
    "record",
    "release",
    "document_hashes",
    "read_published_bytes",
)


class MissingReproductionCatalog(FileNotFoundError):
    """Missing replay evidence is infrastructure failure, not a game rejection."""


def _name(value):
    if not isinstance(value, str) or not value or "\\" in value:
        raise ValueError("Invalid catalog document path")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in ("..", ".", "") for part in value.split("/")):
        raise ValueError("Unsafe catalog document path")
    return value


def _digest(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ValueError("Invalid catalog SHA256")
    return value


def _bytes(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()


def _blob(root, raw):
    if len(raw) > MAX_DOCUMENT_BYTES:
        raise ValueError("Catalog document exceeds size bound")
    digest = hashlib.sha256(raw).hexdigest()
    directory = root / "catalog"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / digest
    if path.exists():
        if path.read_bytes() != raw:
            raise ValueError("Existing catalog blob differs")
    else:
        path.write_bytes(raw)
    return {"sha256": digest, "size": len(raw)}


class _Patch:
    @contextmanager
    def install(self):
        """Patch module methods and previously imported direct aliases temporarily."""
        originals = {key: getattr(native_catalog, key) for key in FUNCTIONS}
        self._originals = originals
        methods = {key: getattr(self, key) for key in FUNCTIONS}
        replacements = {id(value): methods[key] for key, value in originals.items()}
        changed = []
        missing = object()
        alternate_name = "wakfu_server.storage.native_catalog"
        alternate = missing
        parent = None
        parent_attribute = missing
        duplicate = None
        extra_modules = ()
        if getattr(self, "_offline", False):
            # Both names are valid Python import paths in this repository. Bind
            # future explicit storage imports before yielding; also patch old
            # module references and direct function aliases already in memory.
            parent = importlib.import_module("wakfu_server.storage")
            alternate = sys.modules.get(alternate_name, missing)
            parent_attribute = getattr(parent, "native_catalog", missing)
            if alternate is not missing and alternate is not native_catalog:
                duplicate = alternate
                _ACTIVE_CATALOG_DUPLICATES.append(duplicate)
            extra_modules = tuple(_ACTIVE_CATALOG_DUPLICATES)
            for module in extra_modules:
                for key in FUNCTIONS:
                    replacements[id(getattr(module, key))] = methods[key]
            sys.modules[alternate_name] = native_catalog
            parent.native_catalog = native_catalog
        try:
            modules = tuple(sys.modules.values()) + extra_modules
            for module in modules:
                namespace = getattr(module, "__dict__", None)
                if namespace is None or namespace is globals():
                    continue
                for key, value in tuple(namespace.items()):
                    replacement = replacements.get(id(value))
                    if replacement is not None:
                        changed.append((namespace, key, value, replacement))
                        namespace[key] = replacement
            yield self
        finally:
            # Existing aliases must regain their particular original module's
            # function. New aliases regain the canonical pre-context function.
            for namespace, key, original, replacement in reversed(changed):
                if namespace.get(key) is replacement:
                    namespace[key] = original
            reverse = {id(methods[key]): value for key, value in originals.items()}
            modules = tuple(sys.modules.values()) + extra_modules
            for module in modules:
                namespace = getattr(module, "__dict__", None)
                if namespace is None or namespace is globals():
                    continue
                for key, value in tuple(namespace.items()):
                    original = reverse.get(id(value))
                    if original is not None:
                        namespace[key] = original
            if duplicate is not None:
                _ACTIVE_CATALOG_DUPLICATES.pop()
            if parent is not None:
                if sys.modules.get(alternate_name) is native_catalog:
                    if alternate is missing:
                        sys.modules.pop(alternate_name, None)
                    else:
                        sys.modules[alternate_name] = alternate
                if getattr(parent, "native_catalog", missing) is native_catalog:
                    if parent_attribute is missing:
                        delattr(parent, "native_catalog")
                    else:
                        parent.native_catalog = parent_attribute

    def read_text(self, path, encoding="utf8"):
        return self.read_bytes(path).decode(encoding)

    def open(self, path, mode="rt", encoding=None):
        if mode not in ("r", "rt", "rb"):
            raise ValueError("Native catalogs are read-only")
        stream = io.BytesIO(self.read_bytes(path))
        return (
            stream
            if mode == "rb"
            else io.TextIOWrapper(stream, encoding=encoding or "utf8")
        )


class CaptureCatalog(_Patch):
    """Observe existing catalog calls without changing their production results."""

    def __init__(self, extra_documents=()):
        self.documents = {_name(str(name)) for name in extra_documents}
        self.record_results = {}
        self.existence = {}
        self.read_hashes = {}
        self._revision = None

    def __enter__(self):
        self._context = self.install()
        return self._context.__enter__()

    def __exit__(self, *args):
        return self._context.__exit__(*args)

    def _track(self, path):
        name = native_catalog._key(path)
        if name is None:
            return None
        self.release()
        self.documents.add(_name(name))
        return name

    def release(self):
        value = self._originals["release"]()
        if self._revision is not None and value != self._revision:
            raise ValueError("Catalog release changed during capture")
        self._revision = value
        return value

    def document_hashes(self):
        return self._originals["document_hashes"]()

    def read_published_bytes(self, name):
        name = native_catalog._published_document_name(name)
        self.release()
        raw = self._originals["read_published_bytes"](name)
        digest = hashlib.sha256(raw).hexdigest()
        previous = self.read_hashes.setdefault(name, digest)
        if previous != digest:
            raise ValueError("Catalog document changed during capture: " + name)
        self.documents.add(name)
        return raw

    def read_bytes(self, path):
        name = self._track(path)
        raw = self._originals["read_bytes"](path)
        if name is not None:
            digest = hashlib.sha256(raw).hexdigest()
            previous = self.read_hashes.setdefault(name, digest)
            if previous != digest:
                raise ValueError("Catalog document changed during capture: " + name)
        return raw

    def open(self, path, mode="rt", encoding=None):
        self._track(path)
        return self._originals["open"](path, mode, encoding=encoding)

    def load(self, path):
        self._track(path)
        return self._originals["load"](path)

    def exists(self, path):
        name = native_catalog._key(path)
        if name is None:
            return self._originals["exists"](path)
        result = self._originals["exists"](path)
        self.existence[_name(name)] = bool(result)
        if result:
            self.documents.add(name)
        return result

    def record(self, path, collection, record_key):
        name = self._track(path)
        result = self._originals["record"](path, collection, record_key)
        if name is not None:
            self.record_results[(name, str(collection), str(record_key))] = json.loads(
                _bytes(result)
            )
        return result

    def export(self, root):
        """Export read-only SQL bytes and inventory; never fall back to files."""
        root = Path(root)
        root.mkdir(parents=True, exist_ok=True)
        revision = self.release()
        inventory = self.document_hashes()
        for name, digest in inventory.items():
            _name(name)
            _digest(digest)
        documents = {}
        total = 0
        with native_catalog._database().connection() as db:
            for name in sorted(self.documents):
                if name not in inventory:
                    raise ValueError("Consumed catalog missing from release: " + name)
                row = db.execute(
                    "SELECT raw,sha256 FROM native_catalog_documents "
                    "WHERE revision=%s AND path=%s",
                    (revision, name),
                ).fetchone()
                if row is None:
                    raise ValueError("Consumed catalog missing from SQL: " + name)
                raw = bytes(row["raw"])
                if (
                    name in self.read_hashes
                    and self.read_hashes[name] != inventory[name]
                ):
                    raise ValueError(
                        "Consumed bytes differ from published SQL document: " + name
                    )
                if (
                    hashlib.sha256(raw).hexdigest() != inventory[name]
                    or row["sha256"] != inventory[name]
                ):
                    raise ValueError("Published catalog checksum mismatch: " + name)
                total += len(raw)
                if total > MAX_TOTAL_BYTES:
                    raise ValueError("Catalog export exceeds total size bound")
                documents[name] = _blob(root, raw)
        records = [[*key, value] for key, value in sorted(self.record_results.items())]
        manifest = {
            "version": VERSION,
            "authority": "postgresql-published-release",
            "revision": revision,
            "data_root": str(native_catalog.DATA_ROOT.resolve()),
            "published_hashes": inventory,
            "documents": documents,
            "exists": self.existence,
            "records": _blob(root, _bytes(records)),
        }
        raw = _bytes(manifest)
        if len(raw) > MAX_MANIFEST_BYTES:
            raise ValueError("Catalog manifest exceeds size bound")
        (root / "catalog.json").write_bytes(raw)
        return manifest


class ReplayCatalog(_Patch):
    """Only declared, checksum-verified data can be read during replay."""

    _offline = True

    def __init__(self, root):
        self.root = Path(root).resolve()
        path = self.root / "catalog.json"
        if path.stat().st_size > MAX_MANIFEST_BYTES:
            raise ValueError("Catalog manifest exceeds size bound")
        manifest = json.loads(path.read_bytes())
        if (
            manifest.get("version") != VERSION
            or manifest.get("authority") != "postgresql-published-release"
        ):
            raise ValueError("Unsupported catalog provenance/version")
        revision = manifest.get("revision")
        if not isinstance(revision, str) or not revision or len(revision) > 128:
            raise ValueError("Invalid catalog revision")
        self.manifest = manifest
        inventory = manifest["published_hashes"]
        for name, digest in inventory.items():
            _name(name)
            _digest(digest)
        total = 0
        for name, descriptor in manifest["documents"].items():
            _name(name)
            if inventory.get(name) != descriptor["sha256"]:
                raise ValueError("Export does not match published hash inventory")
            total += descriptor["size"]
            self._read_blob(descriptor)
        if total > MAX_TOTAL_BYTES:
            raise ValueError("Catalog replay exceeds total size bound")
        self.records = {
            tuple(row[:3]): row[3]
            for row in json.loads(self._read_blob(manifest["records"]))
        }
        for name, value in manifest["exists"].items():
            _name(name)
            if type(value) is not bool or value != (name in inventory):
                raise ValueError("Invalid catalog existence observation")
        self.decoded = {}

    def _read_blob(self, descriptor):
        digest = _digest(descriptor["sha256"])
        size = descriptor["size"]
        if type(size) is not int or not 0 <= size <= MAX_DOCUMENT_BYTES:
            raise ValueError("Invalid catalog blob size")
        path = self.root / "catalog" / digest
        if (
            path.resolve().parent != (self.root / "catalog").resolve()
            or (self.root / "catalog").resolve().parent != self.root
        ):
            raise ValueError("Catalog blob escapes bundle")
        if path.stat().st_size != size:
            raise ValueError("Catalog blob size mismatch")
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError("Catalog blob checksum mismatch")
        return raw

    def _key(self, path):
        name = native_catalog._key(path)
        if name is None:
            # Captures may originate in a container with another absolute root.
            original_root = self.manifest.get("data_root")
            if original_root:
                try:
                    name = Path(path).relative_to(original_root).as_posix()
                except ValueError:
                    pass
            if name is None:
                raise ValueError("Undeclared external catalog path: " + str(path))
        return _name(name)

    def release(self):
        return self.manifest["revision"]

    def document_hashes(self):
        return dict(self.manifest["published_hashes"])

    def read_published_bytes(self, name):
        name = native_catalog._published_document_name(name)
        if name not in self.manifest["published_hashes"]:
            raise MissingReproductionCatalog("Unpublished replay catalog: " + name)
        if name not in self.manifest["documents"]:
            raise MissingReproductionCatalog("Undeclared replay catalog: " + name)
        return self._read_blob(self.manifest["documents"][name])

    def read_bytes(self, path):
        name = self._key(path)
        if name not in self.manifest["documents"]:
            raise MissingReproductionCatalog("Undeclared replay catalog: " + name)
        return self._read_blob(self.manifest["documents"][name])

    def load(self, path):
        name = self._key(path)
        if name not in self.decoded:
            self.decoded[name] = json.loads(self.read_bytes(path))
        return self.decoded[name]

    def exists(self, path):
        name = self._key(path)
        if name in self.manifest["exists"]:
            return self.manifest["exists"][name]
        if name in self.manifest["documents"]:
            return True
        raise MissingReproductionCatalog("Undeclared replay catalog existence: " + name)

    def record(self, path, collection, record_key):
        key = (self._key(path), str(collection), str(record_key))
        if key not in self.records:
            raise MissingReproductionCatalog("Undeclared replay record: " + repr(key))
        return self.records[key]
