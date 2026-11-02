"""Bounded immutable rotation parts after pinned-source hash validation.

Cache only geometry/roster/evidence. Session, instance, actor, key ownership,
frontier, context and level policy are never retained in a shared projection.
"""
from collections import OrderedDict
from copy import deepcopy
from threading import RLock
from wakfu_server import dungeon_rotation


def _immutable(*args, **kwargs):
    raise TypeError("Pinned rotation parts are read-only")


class _ReadOnlyDict(dict):
    __slots__ = ()
    __setitem__ = (
        __delitem__
    ) = clear = pop = popitem = setdefault = update = __ior__ = _immutable

    def __copy__(self):
        return self

    def __deepcopy__(self, memo):
        return self


class _ReadOnlyList(list):
    __slots__ = ()
    __setitem__ = (
        __delitem__
    ) = (
        append
    ) = (
        extend
    ) = insert = pop = remove = reverse = sort = __iadd__ = __imul__ = _immutable

    def __copy__(self):
        return self

    def __deepcopy__(self, memo):
        return self


def _freeze(value):
    if isinstance(value, dict):
        return _ReadOnlyDict({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return _ReadOnlyList(_freeze(item) for item in value)
    return value


_PARTS = OrderedDict()
_LOCK = RLock()
_MAX_PARTS = 6
_PENDING = frozenset(("_rotation_pending", "_rotation_key_character_id"))


def clear():
    """Reset the bounded process cache, including independent test fixtures."""
    with _LOCK:
        _PARTS.clear()


def project_pinned(config, selector):
    """Call only after pinned_configuration validates original source hashes.

    JSON-compatible read-only parts prevent one caller from poisoning another
    instance's terrain. Dynamic source projections deliberately use no cache.
    """
    if type(selector) is not int or selector <= 0:
        raise ValueError("Invalid native rotation selector")
    topology = config["topology"]
    if topology.get("selected_rotation") is not None:
        raise ValueError("Rotation cache requires original pinned source")
    clean = {key: value for key, value in topology.items() if key not in _PENDING}
    source = dict(config, topology=clean)
    evidence = config.get("evidence_hashes", {})
    checksums = tuple(evidence.get(field) for field in ("plan", "topology", "route"))
    valid = all(
        isinstance(value, str)
        and len(value) == 64
        and all(c in "0123456789abcdef" for c in value)
        for value in checksums
    )
    if not valid or any(key.startswith("_") for key in clean):
        return dungeon_rotation.project(source, selector)
    key = (*checksums, selector)
    with _LOCK:
        parts = _PARTS.get(key)
        if parts is None:
            projected = dungeon_rotation.project(source, selector)
            parts = _freeze(
                {
                    name: projected[name]
                    for name in (
                        "compiled_plan",
                        "topology",
                        "evidence_hashes",
                        "projection_source_evidence_hashes",
                    )
                }
            )
            _PARTS[key] = parts
            while len(_PARTS) > _MAX_PARTS:
                _PARTS.popitem(last=False)
        else:
            _PARTS.move_to_end(key)
    bound = {
        name: deepcopy(value) for name, value in config.items() if name not in parts
    }
    bound.update(parts)
    return bound
