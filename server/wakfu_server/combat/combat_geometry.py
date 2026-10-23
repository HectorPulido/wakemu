"""Immutable validated native geometry shared across encounter selections."""
from collections import OrderedDict, defaultdict, deque
from dataclasses import dataclass
from functools import lru_cache
from types import MappingProxyType
from threading import RLock

from wakfu_server import native_catalog as protocol_catalog
from wakfu_server.paths import DATA_ROOT


def coordinate(value):
    if isinstance(value, dict):
        value = value.get("position", (value.get("x"), value.get("y"), value.get("z")))
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ValueError("Invalid arena participant or topology coordinate")
    x, y, z = value
    if (
        any(type(n) is not int for n in value)
        or not -(1 << 31) <= x < (1 << 31)
        or not -(1 << 31) <= y < (1 << 31)
        or not -(1 << 15) <= z < (1 << 15)
    ):
        raise ValueError("Arena coordinate is outside native bounds")
    return x, y, z


@dataclass(frozen=True, slots=True)
class PreparedGeometry:
    map_id: int
    cells: frozenset
    edges: frozenset
    outgoing: object
    incoming: object


def prepare_geometry(data):
    """Snapshot mutable callers afresh; only explicit prepared values are reused."""
    if isinstance(data, PreparedGeometry):
        return data
    if not isinstance(data, dict) or type(data.get("map_id")) is not int:
        raise ValueError("Arena requires exported map metadata")
    cells = frozenset(coordinate(cell) for cell in data["cells"])
    edges = set()
    outgoing, incoming = defaultdict(set), defaultdict(set)
    for edge in data["edges"]:
        if not isinstance(edge, (list, tuple)) or len(edge) != 2:
            raise ValueError("Invalid native topology edge")
        start, end = map(coordinate, edge)
        if (
            start not in cells
            or end not in cells
            or abs(start[0] - end[0]) + abs(start[1] - end[1]) != 1
        ):
            raise ValueError("Native topology edge is missing or nonadjacent")
        edges.add((start, end))
        outgoing[start].add(end)
        incoming[end].add(start)
    return PreparedGeometry(
        data["map_id"],
        cells,
        frozenset(edges),
        MappingProxyType(
            {cell: tuple(sorted(values)) for cell, values in outgoing.items()}
        ),
        MappingProxyType(
            {cell: tuple(sorted(values)) for cell, values in incoming.items()}
        ),
    )


def reachable(origin, cells, adjacency):
    """Traverse an induced native subgraph without rebuilding map adjacency."""
    reached = {origin}
    pending = deque([origin])
    while pending:
        current = pending.popleft()
        if current not in cells:
            continue
        for target in adjacency.get(current, ()):
            if target in cells and target not in reached:
                reached.add(target)
                pending.append(target)
    return reached


# Keys use identity, not map IDs: distinct exports may share a map ID. Each
# entry retains the immutable geometry, preventing identity reuse while cached.
_ENCOUNTER_COMPONENT_LIMIT = 32
_encounter_components = OrderedDict()
_encounter_components_lock = RLock()


def _compute_encounter_component(geometry, origin):
    if origin not in geometry.cells:
        raise ValueError("Player is outside native encounter terrain")
    selected = reachable(origin, geometry.cells, geometry.outgoing) & reachable(
        origin, geometry.cells, geometry.incoming
    )
    columns = defaultdict(list)
    for cell in selected:
        columns[cell[:2]].append(cell)
    ambiguous = {xy for xy, values in columns.items() if len(values) > 1}
    if origin[:2] in ambiguous:
        raise ValueError("Player occupies ambiguous native encounter surface")
    selected = {cell for cell in selected if cell[:2] not in ambiguous}
    selected = reachable(origin, selected, geometry.outgoing) & reachable(
        origin, selected, geometry.incoming
    )
    return frozenset(selected), frozenset(ambiguous)


def encounter_component(data, origin, *, memoize=True):
    """Return fresh sets for the native mutual component after column pruning.

    Only explicit immutable prepared snapshots are memoized. Mutable dictionary
    callers are snapshotted and traversed anew, even when their map ID matches.
    Formation, budgets and local induced-subgraph traversal remain per encounter.
    """
    prepared = memoize and isinstance(data, PreparedGeometry)
    geometry = prepare_geometry(data)
    key = (id(geometry), origin)
    if prepared:
        with _encounter_components_lock:
            cached = _encounter_components.get(key)
            if cached is not None and cached[0] is geometry:
                _encounter_components.move_to_end(key)
                return set(cached[1]), set(cached[2])
    selected, ambiguous = _compute_encounter_component(geometry, origin)
    if prepared:
        with _encounter_components_lock:
            _encounter_components[key] = (geometry, selected, ambiguous)
            _encounter_components.move_to_end(key)
            while len(_encounter_components) > _ENCOUNTER_COMPONENT_LIMIT:
                _encounter_components.popitem(last=False)
    return set(selected), set(ambiguous)


def edges_within(cells, adjacency):
    return {
        (start, end)
        for start in cells
        for end in adjacency.get(start, ())
        if end in cells
    }


@lru_cache(maxsize=16)
def _published_geometry(revision, map_id):
    # The revision is pinned by native_catalog. Mutable dictionaries from
    # map_geometry callers are never keys or sources of this reusable cache.
    from wakfu_server.prepared_geometry import published_artifact
    from wakfu_server.haven_world_terrain import TEMPLATE_MAP_ID, geometry

    if map_id == TEMPLATE_MAP_ID:
        if protocol_catalog.exists(DATA_ROOT / "combat-maps" / f"{map_id}.json"):
            raise ValueError("Internal Haven World geometry namespace collision")
        return prepare_geometry(geometry())
    artifact = published_artifact(map_id)
    if artifact is not None:
        return artifact.geometry
    path = DATA_ROOT / "combat-maps" / f"{map_id}.json"
    if not protocol_catalog.exists(path):
        raise ValueError("No installed-client geometry export for this map")
    data = protocol_catalog.load(path)
    if data.get("map_id") != map_id:
        raise ValueError("Combat map export identity mismatch")
    return prepare_geometry(data)


def published_geometry(map_id):
    if type(map_id) is not int or map_id <= 0:
        raise ValueError("Invalid combat map identity")
    return _published_geometry(protocol_catalog.release(), map_id)
