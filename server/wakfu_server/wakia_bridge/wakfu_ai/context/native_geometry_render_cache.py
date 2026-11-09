"""Bounded exact render reuse for verified immutable geometry fragments."""
from collections import OrderedDict
from sys import getsizeof
from threading import RLock
from weakref import ref

from ..native.native_deadline import check
from .native_geometry_fragments import _locked

_CACHE = OrderedDict()
_LOCK = RLock()
_BYTES = 0
_MAX_ENTRIES = 4
_MAX_BYTES = 16 * 1024 * 1024


def _charge(refmap, emitted, rows):
    """Conservatively charge the known immutable render schema.

    Row indices are the same int objects already owned by refmap. Literal
    strings may be shared by templates; charging them per row is conservative.
    """
    size = getsizeof(refmap) + getsizeof(emitted) + getsizeof(rows) + 256
    for values in (refmap, emitted):
        for index, value in enumerate(values):
            if index % 1024 == 0:
                check()
            size += getsizeof(value)
            if size > _MAX_BYTES:
                return None
    for index, row in enumerate(rows):
        if index % 1024 == 0:
            check()
        size += getsizeof(row) + getsizeof(row[1])
        if size > _MAX_BYTES:
            return None
    return size


def rebase_fragment(fragment, identities, next_index):
    """Recompute all current aliases; reuse bytes only for the exact full map."""
    global _BYTES
    # Always execute the original complete identity assignment and validation.
    # Equal coordinates cannot replace distinct identities, and aliases outside
    # this fragment still determine which complete graph owns each row.
    refmap, following, assignments, emitted = fragment.identity_map(
        identities, next_index
    )
    key = id(fragment), hash(refmap), hash(emitted)
    with _locked(_LOCK):
        cached = _CACHE.get(key)
        if (
            cached is not None
            and cached[0]() is fragment
            and cached[1] == refmap
            and cached[2] == emitted
        ):
            _CACHE.move_to_end(key)
            return refmap[0], following, assignments, cached[3]
    rows = []
    for local, template in enumerate(fragment.templates):
        if local % 1024 == 0:
            check()
        if local == 0 or local in emitted:
            rows.append((refmap[local], template.format(refmap)))
    rows = tuple(rows)
    charge = _charge(refmap, emitted, rows)
    if charge is not None:
        with _locked(_LOCK):
            previous = _CACHE.pop(key, None)
            if previous is not None:
                _BYTES -= previous[4]
            _CACHE[key] = ref(fragment), refmap, emitted, rows, charge
            _BYTES += charge
            while len(_CACHE) > _MAX_ENTRIES or _BYTES > _MAX_BYTES:
                _, previous = _CACHE.popitem(last=False)
                _BYTES -= previous[4]
    check()
    return refmap[0], following, assignments, rows


def clear():
    global _BYTES
    with _locked(_LOCK):
        _CACHE.clear()
        _BYTES = 0
