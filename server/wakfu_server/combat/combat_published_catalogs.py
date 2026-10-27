"""Sealed, pinned static mappings backed by published compiled records.

Descriptors contain immutable publication identities only. Database handles,
cache contents and decoded definitions never enter transport fingerprints.
"""
from collections import OrderedDict
from collections.abc import Mapping
from threading import RLock
import json
import os
import weakref
from types import MappingProxyType
from itertools import islice
from contextlib import contextmanager
from contextvars import ContextVar

from .combat_static_catalogs import _freeze

POLICY = "wakemu.published-static-collection.v1"
_FIELDS = frozenset(
    (
        "policy",
        "revision",
        "manifest_sha256",
        "collection",
        "count",
        "ordered_keys_sha256",
    )
)
_SEAL = object()
_LOCK = RLock()
_LIVE_ROWS = {}
_HOT_ROWS = OrderedDict()
_HOT_BYTES = 0
_HOT_MAX_BYTES = 8 * 1024 * 1024
_HOT_MAX_ENTRIES = 512
_SCALAR_ROWS = OrderedDict()
_SCALAR_MAX_ENTRIES = 8192
_OFFLINE_COMPILATION = ContextVar("wakemu_offline_catalog_compilation", default=False)


def compilation_mode():
    """Only an explicit build child/context may materialize original sources."""
    return (
        _OFFLINE_COMPILATION.get() is True
        or os.environ.get("WAKFU_COMPILED_CATALOG_BUILD") == "1"
    )


compiling_catalog_offline = compilation_mode


@contextmanager
def offline_catalog_compilation():
    """Explicit publisher-only source compilation, never a runtime fallback."""
    token = _OFFLINE_COMPILATION.set(True)
    try:
        yield
    finally:
        _OFFLINE_COMPILATION.reset(token)


def _sha(value):
    return (
        type(value) is str
        and len(value) == 64
        and all(char in "0123456789abcdef" for char in value)
    )


def validate_static_catalog_descriptor(record):
    """Validate canonical transport metadata without I/O or trusting its claim."""
    if type(record) is not dict or set(record) != _FIELDS:
        raise ValueError("Invalid published static descriptor shape")
    if (
        record["policy"] != POLICY
        or not _sha(record["revision"])
        or record["manifest_sha256"] != record["revision"]
        or not _sha(record["ordered_keys_sha256"])
        or type(record["count"]) is not int
        or record["count"] < 0
    ):
        raise ValueError("Invalid published static descriptor identity")
    collection = record["collection"]
    if (
        type(collection) is not str
        or not collection
        or "\\" in collection
        or "\0" in collection
        or any(part in ("", ".", "..") for part in collection.split("/"))
    ):
        raise ValueError("Invalid published static collection")
    return {key: record[key] for key in sorted(_FIELDS)}


def static_catalog_descriptor(value):
    if (
        type(value) is not PublishedStaticMapping
        or getattr(value, "_seal", None) is not _SEAL
    ):
        return None
    return dict(value._descriptor)


def resolve_static_catalog_descriptor(record):
    """Resolve the exact generation, requiring an authoritative complete manifest."""
    descriptor = validate_static_catalog_descriptor(record)
    from wakfu_server.native_compiled_catalog import published_collection

    reader = published_collection(descriptor)
    if validate_static_catalog_descriptor(reader.descriptor) != descriptor:
        raise ValueError("Published static reader returned a different generation")
    if reader.representation not in ("native_json", "frozen_effect"):
        raise ValueError("Unknown published static record representation")
    return PublishedStaticMapping(descriptor, reader, _seal=_SEAL)


def published_original_output_index(value):
    """Read the compiler's small original-output proof without effect scans."""
    if static_catalog_descriptor(value) is None:
        raise TypeError("Original output proof requires a sealed static mapping")
    if value.representation != "frozen_effect":
        return MappingProxyType({})
    rows = value._reader.original_output_index()
    if not isinstance(rows, (tuple, list)):
        raise ValueError("Missing published original output index")
    result = {}
    for row in rows:
        if (
            not isinstance(row, (tuple, list))
            or len(row) != 3
            or type(row[0]) is not str
            or not row[0]
            or type(row[1]) is not int
            or not isinstance(row[2], (tuple, list))
            or not row[2]
            or any(type(event) is not int or event < 0 for event in row[2])
            or row[0] in result
        ):
            raise ValueError("Invalid published original output identity")
        result[row[0]] = (row[1], frozenset(row[2]))
    return MappingProxyType(result)


def static_row_scalar(catalog, key, field, *, default=None):
    """Project immutable scalar metadata, without memoizing any actor/book.

    Raw record reads still return fresh dict/list objects. Only the requested
    scalar (or proven missing row) is retained under its exact publication pin.
    """
    sealed = (
        type(catalog) is PublishedStaticMapping
        and getattr(catalog, "_seal", None) is _SEAL
        and catalog.representation == "native_json"
    )
    cache_key = None
    if (
        sealed
        and type(key) is str
        and type(field) is str
        and len(key) <= 256
        and len(field) <= 128
    ):
        cache_key = (
            catalog._descriptor["revision"],
            catalog._descriptor["collection"],
            key,
            field,
        )
        with _LOCK:
            if cache_key in _SCALAR_ROWS:
                present, value = _SCALAR_ROWS[cache_key]
                _SCALAR_ROWS.move_to_end(cache_key)
                return value if present else default
    definition = catalog.get(key)
    present = definition is not None
    value = definition.get(field) if present else None
    cacheable = (
        value is None
        or type(value) in (bool, int, float)
        or type(value) is str
        and len(value) <= 1024
    )
    if cache_key is not None and cacheable:
        with _LOCK:
            _SCALAR_ROWS[cache_key] = (present, value)
            _SCALAR_ROWS.move_to_end(cache_key)
            while len(_SCALAR_ROWS) > _SCALAR_MAX_ENTRIES:
                _SCALAR_ROWS.popitem(last=False)
    return value if present else default


def _clear_static_scalars():
    with _LOCK:
        _SCALAR_ROWS.clear()


static_row_scalar.cache_clear = _clear_static_scalars


def _remember(key, value, raw_size):
    """Bound the hot set; weak identities remain stable while callers hold rows."""
    global _HOT_BYTES
    try:

        def discard(reference):
            with _LOCK:
                if _LIVE_ROWS.get(key) is reference:
                    _LIVE_ROWS.pop(key, None)

        reference = weakref.ref(value, discard)
    except TypeError:
        reference = None
    if reference is not None:
        _LIVE_ROWS[key] = reference
    # This bounds retained canonical-source bytes, not total process RSS.
    if raw_size <= _HOT_MAX_BYTES:
        previous = _HOT_ROWS.pop(key, None)
        if previous is not None:
            _HOT_BYTES -= previous[1]
        _HOT_ROWS[key] = (value, raw_size)
        _HOT_BYTES += raw_size
        while _HOT_BYTES > _HOT_MAX_BYTES or len(_HOT_ROWS) > _HOT_MAX_ENTRIES:
            _, (_, size) = _HOT_ROWS.popitem(last=False)
            _HOT_BYTES -= size


class PublishedStaticMapping(Mapping):
    """Original ordered collection; construction never loads all its records."""

    __slots__ = ("_descriptor", "_reader", "_seal")

    def __init__(self, descriptor, reader, *, _seal=None):
        if _seal is not _SEAL:
            raise TypeError("Published static views require authoritative resolution")
        object.__setattr__(self, "_descriptor", MappingProxyType(dict(descriptor)))
        object.__setattr__(self, "_reader", reader)
        object.__setattr__(self, "_seal", _SEAL)

    def __setattr__(self, name, value):
        raise TypeError("Published static mapping is immutable")

    def __len__(self):
        return self._descriptor["count"]

    @property
    def representation(self):
        return self._reader.representation

    def __iter__(self):
        return iter(self._reader)

    def __contains__(self, key):
        return type(key) is str and key in self._reader

    def __getitem__(self, key):
        if type(key) is not str:
            raise KeyError(key)
        if self._reader.representation == "native_json":
            # Original source consumers require dict/list, and may prepare a
            # private derivative. Never share their mutable decoded objects.
            return self._from_verified_bytes(key, self._reader.record_bytes(key))
        identity = (self._descriptor["revision"], self._descriptor["collection"], key)
        with _LOCK:
            hot = _HOT_ROWS.get(identity)
            if hot is not None:
                _HOT_ROWS.move_to_end(identity)
                return hot[0]
            reference = _LIVE_ROWS.get(identity)
            existing = None if reference is None else reference()
            if existing is not None:
                return existing
        raw = self._reader.record_bytes(key)
        return self._from_verified_bytes(key, raw)

    def _from_verified_bytes(self, key, raw):
        if type(raw) is not bytes:
            raise TypeError("Published static records require verified canonical bytes")
        if self._reader.representation == "native_json":
            return json.loads(raw)
        identity = (self._descriptor["revision"], self._descriptor["collection"], key)
        with _LOCK:
            reference = _LIVE_ROWS.get(identity)
            existing = None if reference is None else reference()
            if existing is not None:
                return existing
            hot = _HOT_ROWS.get(identity)
            if hot is not None:
                _HOT_ROWS.move_to_end(identity)
                return hot[0]
        value = _freeze(json.loads(raw))
        with _LOCK:
            reference = _LIVE_ROWS.get(identity)
            existing = None if reference is None else reference()
            if existing is not None:
                return existing
            hot = _HOT_ROWS.get(identity)
            if hot is not None:
                _HOT_ROWS.move_to_end(identity)
                return hot[0]
            _remember(identity, value, len(raw))
        return value

    def _batch_items(self, keys):
        from wakfu_server.native_compiled_catalog import CompiledBatchLimit

        try:
            rows = self._reader.get_many_bytes(keys)
        except CompiledBatchLimit:
            if len(keys) <= 1:
                raise
            middle = len(keys) // 2
            yield from self._batch_items(keys[:middle])
            yield from self._batch_items(keys[middle:])
            return
        for key in keys:
            if key not in rows:
                raise ValueError("Published ordered collection lacks its record")
            yield key, self._from_verified_bytes(key, rows[key])

    def items(self):
        """Stream bounded batches; key-only iteration never fetches records."""
        keys = iter(self)
        while batch := tuple(islice(keys, 128)):
            yield from self._batch_items(batch)

    def values(self):
        return (value for _, value in self.items())

    def __deepcopy__(self, memo):
        memo[id(self)] = self
        return self
