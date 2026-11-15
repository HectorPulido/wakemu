"""Immutable, evidence-bound geometry snapshots for native navigation handles."""

import hashlib
import json


def _immutable(*args, **kwargs):
    raise TypeError("Pinned spatial geometry is immutable")


class _FrozenList(list):
    __slots__ = ("_initialized",)
    __setattr__ = __delattr__ = _immutable

    def __init__(self, values):
        if hasattr(self, "_initialized"):
            _immutable()
        list.__init__(self, values)
        object.__setattr__(self, "_initialized", True)

    __setitem__ = __delitem__ = append = clear = extend = insert = pop = remove = (
        reverse
    ) = sort = __iadd__ = __imul__ = _immutable

    def __deepcopy__(self, memo):
        return self


class FrozenGeometry(dict):
    """JSON-compatible snapshot created only after dungeon evidence validation."""

    __slots__ = ("_authority",)
    __setitem__ = __delitem__ = clear = pop = popitem = setdefault = update = (
        __ior__
    ) = _immutable
    __setattr__ = __delattr__ = _immutable

    def __init__(self, geometry, authority):
        if hasattr(self, "_authority"):
            _immutable()
        dict.__init__(self, ((key, _freeze(value)) for key, value in geometry.items()))
        object.__setattr__(self, "_authority", authority)

    @property
    def authority(self):
        return self._authority

    def __deepcopy__(self, memo):
        return self


def _freeze(value):
    if isinstance(value, dict):
        return FrozenGeometry(value, None)
    if isinstance(value, (list, tuple)):
        return _FrozenList(_freeze(item) for item in value)
    return value


def freeze_geometry(geometry, authority):
    if isinstance(geometry, FrozenGeometry):
        return geometry
    return FrozenGeometry(geometry, authority)


def digest(value):
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode()
    ).hexdigest()


def directed_path(native, geometry, request, blocked, *, allowed_cells=None):
    """Reuse attested native graphs; mutable synthetic inputs stay uncached."""
    if not isinstance(geometry, FrozenGeometry):
        return native.call(
            "navigation.directed_path",
            request=request,
            cells=geometry["cells"] if allowed_cells is None else sorted(allowed_cells),
            edges=geometry["edges"],
            blocked=sorted(blocked),
        )
    authority = geometry.authority
    if allowed_cells is not None:
        authority += ":allowed:" + digest(sorted(allowed_cells))
    # A concurrent registration can evict a handle between lookup and use.
    # Retry once before any movement is committed; never bypass validation.
    for attempt in range(2):
        key = native.call("navigation.topology_lookup", authority=authority)["key"]
        if key is None:
            arguments = dict(
                authority=authority, cells=geometry["cells"], edges=geometry["edges"]
            )
            if allowed_cells is not None:
                arguments["allowed_cells"] = sorted(allowed_cells)
            key = native.call("navigation.topology_register", **arguments)["key"]
        try:
            return native.call(
                "navigation.directed_path",
                topology_key=key,
                request=request,
                blocked=sorted(blocked),
            )
        except ValueError as error:
            if attempt or str(error) != "Navigation topology handle expired":
                raise
