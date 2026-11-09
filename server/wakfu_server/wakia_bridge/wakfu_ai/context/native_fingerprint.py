"""Fast complete local fingerprints; these bytes are never deserialized.

Builtin container traversal runs in the C pickler. Native object reducers are
replaced with explicit instance fields, so custom __reduce__ methods cannot
hide fields or execute. References and cycles remain in the memo. The public
lossless graph remains the transport format; this is only a local guard.
"""
import hashlib
import inspect
import pickle
import json
from datetime import date, datetime
from decimal import Decimal
from collections import deque
from weakref import ReferenceType
from threading import RLock
from contextlib import contextmanager
from contextvars import ContextVar


class NativeLineages:
    """Keep exact opaque tokens for one Oracle lifetime, without holding fights."""

    def __init__(self, maximum=128):
        self.maximum = maximum
        self.lock = RLock()
        self.entries = {}

    def token(self, lineage):
        if type(lineage) is not object:
            raise ValueError("Invalid native pointer lineage")
        key = id(lineage)
        with self.lock:
            entry = self.entries.get(key)
            if entry is None:
                if len(self.entries) >= self.maximum:
                    raise ValueError(
                        "Native pointer lineage fingerprint capacity exceeded"
                    )
                entry = (lineage, len(self.entries) + 1)
                self.entries[key] = entry
            elif entry[0] is not lineage:
                raise ValueError("Native pointer lineage identity collision")
            return entry[1]


_LINEAGE_SCOPE = ContextVar("wakia_native_lineage_scope", default=None)


@contextmanager
def lineage_scope(lineages):
    token = _LINEAGE_SCOPE.set(lineages)
    try:
        yield
    finally:
        _LINEAGE_SCOPE.reset(token)


from .native_context import (
    _instance_fields,
    _LOCK_TYPES,
    _lock_fields,
    _static_catalog_descriptor,
)
from ..native.native_deadline import check


def _record(*descriptor):
    raise RuntimeError("Native fingerprint bytes must never be deserialized")


class _CompletePickler(pickle.Pickler):
    def reducer_override(self, value):
        # Primitive containers run in C; the output writer checks their frames.
        # Native reducers also check so an object-heavy graph remains bounded.
        check()
        if value is _record:
            return NotImplemented
        kind = type(value)
        static_descriptor = _static_catalog_descriptor(value)
        if static_descriptor is not None:
            return _record, (
                "staticCatalog",
                json.dumps(
                    static_descriptor,
                    sort_keys=True,
                    separators=(",", ":"),
                    allow_nan=False,
                ),
            )
        if isinstance(value, _LOCK_TYPES):
            return (
                _record,
                ("nativeAuthority", kind.__module__, kind.__qualname__),
                _lock_fields(value),
            )
        if inspect.isroutine(value):
            return _record, (
                "callable",
                getattr(value, "__module__", kind.__module__),
                getattr(value, "__qualname__", kind.__qualname__),
            )
        if isinstance(value, datetime):
            return _record, ("datetime", value.isoformat(), value.fold)
        if isinstance(value, date):
            return _record, ("date", value.isoformat())
        if isinstance(value, Decimal):
            return _record, ("decimal", str(value))
        if isinstance(value, memoryview):
            return _record, ("memoryview", bytes(value))
        if kind is ReferenceType:
            # Exact builtin dereference only reads its current referent. It does
            # not invoke the finalization callback. Keep both graph edges in
            # the pickler memo rather than omitting derived native owners.
            return _record, ("weakref", value(), value.__callback__)
        if isinstance(value, ReferenceType):
            raise ValueError(
                "Unsupported complete fingerprint type: " + kind.__qualname__
            )
        fields = _instance_fields(value)
        if (
            kind.__module__ == "wakfu_server.combat_pointer_qi_checkpoint"
            and kind.__qualname__ == "NativePointerCheckpoint"
        ):
            from wakfu_server.combat_pointer_qi_checkpoint import (
                NativePointerCheckpoint,
            )

            if kind is NativePointerCheckpoint:
                if self.lineages is None:
                    raise ValueError("Missing local native pointer lineage scope")
                fields = dict(fields)
                fields["_lineage"] = (
                    "native-pointer-lineage-v1",
                    self.lineages.token(fields.get("_lineage")),
                )
        descriptor = kind.__module__, kind.__qualname__
        if isinstance(value, dict):
            return (
                _record,
                ("dict", *descriptor),
                fields or None,
                None,
                # Inspect stored state without invoking a lazy or custom view.
                iter(dict.items(value)),
            )
        if isinstance(value, (list, tuple, set, frozenset)):
            container = next(
                cls.__name__
                for cls in (list, tuple, set, frozenset)
                if isinstance(value, cls)
            )
            return _record, (container, *descriptor), fields or None, iter(value)
        if isinstance(value, deque):
            return (
                _record,
                ("deque", *descriptor, value.maxlen),
                fields or None,
                iter(value),
            )
        if not fields and not hasattr(value, "__dict__"):
            raise ValueError(
                "Unsupported complete fingerprint type: " + kind.__qualname__
            )
        return _record, ("object", *descriptor), fields


class _HashWriter:
    """Hash the exact pickle stream without retaining a second graph in memory."""

    def __init__(self):
        self.digest = hashlib.sha256()

    def write(self, payload):
        # Pickle emits bounded frames for ordinary graph traversal. Large raw
        # buffers may be emitted directly, so hash those in bounded blocks too.
        view = memoryview(payload)
        for offset in range(0, len(view), 64 * 1024):
            check()
            self.digest.update(view[offset : offset + 64 * 1024])
        return len(view)


def fingerprint(value):
    check()
    stream = _HashWriter()
    pickler = _CompletePickler(stream, protocol=5)
    pickler.lineages = _LINEAGE_SCOPE.get()
    pickler.dump(value)
    check()
    return stream.digest.hexdigest()
