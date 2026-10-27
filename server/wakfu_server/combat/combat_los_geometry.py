"""Prepared immutable LOS domain, bound to actual current terrain contents."""
from dataclasses import dataclass
from threading import RLock
from weakref import WeakKeyDictionary


_SEAL = object()
_LOCK = RLock()
_PROOFS = WeakKeyDictionary()


class PreparedLosGeometry:
    """Opaque local observation token; callers cannot supply geometry fields."""

    __slots__ = ("__weakref__",)

    def __new__(cls, *, _seal=None):
        if _seal is not _SEAL:
            raise TypeError("LOS geometry requires its actual terrain constructor")
        return super().__new__(cls)


@dataclass(frozen=True)
class _GeometryFacts:
    map_id: int
    walkable: object
    cells: frozenset
    permitted_xy: frozenset


def prepare_los_geometry(map_id, walkable):
    """Snapshot exact owned integer terrain; unknown inputs retain strict reads."""
    if type(map_id) is not int or type(walkable) not in (set, frozenset):
        return None
    cells = frozenset(walkable)
    if any(
        type(cell) is not tuple
        or len(cell) != 3
        or any(type(value) is not int for value in cell)
        for cell in cells
    ):
        return None
    facts = _GeometryFacts(
        map_id, walkable, cells, frozenset((cell[0], cell[1]) for cell in cells)
    )
    token = PreparedLosGeometry(_seal=_SEAL)
    with _LOCK:
        _PROOFS[token] = facts
    return token


def prepared_permitted_xy(token, *, map_id, walkable):
    """Check object ownership and current C-level set equality on every use."""
    if type(token) is not PreparedLosGeometry:
        return None
    with _LOCK:
        facts = _PROOFS.get(token)
    if (
        facts is None
        or type(map_id) is not int
        or map_id != facts.map_id
        or walkable is not facts.walkable
        or type(walkable) not in (set, frozenset)
        or walkable != facts.cells
    ):
        return None
    return facts.permitted_xy
