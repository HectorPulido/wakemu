"""Fast complete local fingerprints; these bytes are never deserialized.

Builtin container traversal runs in the C pickler. Native object reducers are
replaced with explicit instance fields, so custom __reduce__ methods cannot
hide fields or execute. References and cycles remain in the memo. The public
lossless graph remains the transport format; this is only a local guard.
"""
import hashlib
import inspect
import io
import pickle
from datetime import date, datetime
from decimal import Decimal
from collections import deque

if __package__:
    from .native_context import _instance_fields, _LOCK_TYPES, _lock_fields
else:
    from native_context import _instance_fields, _LOCK_TYPES, _lock_fields


def _record(*descriptor):
    raise RuntimeError("Native fingerprint bytes must never be deserialized")


class _CompletePickler(pickle.Pickler):
    def reducer_override(self, value):
        if value is _record:
            return NotImplemented
        kind = type(value)
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
        fields = _instance_fields(value)
        descriptor = kind.__module__, kind.__qualname__
        if isinstance(value, dict):
            return (
                _record,
                ("dict", *descriptor),
                fields or None,
                None,
                iter(value.items()),
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


def fingerprint(value):
    stream = io.BytesIO()
    _CompletePickler(stream, protocol=5).dump(value)
    return hashlib.sha256(stream.getbuffer()).hexdigest()
