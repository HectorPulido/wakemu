"""Consumer-backed ordinary combat floor policy, separate from native physics.

Original Sn accepts some invisible authoring surfaces. This reviewed Wakemu
reconstruction adds original selectable/non-overlay/nonempty simple graphics.
Unknown materials retain physics; scripted selected-area births stay distinct.
"""
from collections import deque
from functools import lru_cache
from pathlib import Path
import json


@lru_cache(maxsize=1)
def _catalog():
    value = json.loads(
        Path(__file__).with_name("combat_ground_support.json").read_text()
    )
    if value.get("schema") != "wakemu-native-renderable-ground-support-v1":
        raise ValueError("Unknown ordinary combat floor publication")
    return value


@lru_cache(maxsize=128)
def _map(map_id, source_sha256, release):
    catalog = _catalog()
    if catalog["qualified_native_release"] != release:
        raise ValueError("Ordinary combat floor native publication changed")
    row = catalog["maps"].get(str(map_id))
    if row is None or row["status"] != "exported":
        return None
    if row["map_id"] != map_id or row["source_sha256"] != source_sha256:
        raise ValueError("Ordinary combat floor physical source changed")
    supported = frozenset(map(tuple, row["supported_cells"]))
    unknown = frozenset(map(tuple, row["unknown_material_cells"]))
    if any(
        len(cell) != 3 or any(type(n) is not int for n in cell)
        for cell in supported | unknown
    ):
        raise ValueError("Malformed ordinary combat floor cell")
    return supported | unknown


def supported(map_id, cell, source_sha256):
    """Unknown maps/materials preserve existing physics, never attest emptiness."""
    from wakfu_server import native_catalog

    cells = _map(map_id, source_sha256, native_catalog.release())
    return cells is None or tuple(cell) in cells


def fight_supported(fight, cell):
    provenance = getattr(fight, "native_qi_surface_provenance", None)
    if provenance is None:
        return True
    if not isinstance(provenance, dict) or type(provenance.get("map_id")) is not int:
        raise ValueError("Missing ordinary combat floor provenance")
    return supported(provenance["map_id"], cell, provenance.get("source_sha256"))


def require_walk(fight, actor, path, *, air_crossing_cells=()):
    """Validate destinations; an old/teleported occupant may leave its pocket.

    A full escape path must end on supported floor. Once supported floor is
    reached, the same paid request cannot reenter unsupported ground. Source-
    qualified native85 air crossings are intermediate steps, never landings.
    """
    if not path:
        return
    crossing = frozenset(air_crossing_cells)
    if not fight_supported(fight, path[-1]):
        raise ValueError("Ordinary walking must end on a qualified combat floor")
    escaped = fight_supported(fight, actor.position)
    for cell in path:
        if fight_supported(fight, cell):
            escaped = True
        elif cell not in crossing and escaped:
            raise ValueError("Ordinary walking enters a non-rendered combat floor")


def escape_prefix_cells(fight, actor):
    """Only the connected unsupported source pocket may be traversed to exit."""
    if fight_supported(fight, actor.position):
        return frozenset()
    unsupported = {cell for cell in fight.walkable if not fight_supported(fight, cell)}
    adjacent = {}
    for a, b in fight.edges or ():
        if a in unsupported and b in unsupported:
            adjacent.setdefault(a, []).append(b)
    reached = {actor.position}
    queue = deque((actor.position,))
    while queue:
        for cell in adjacent.get(queue.popleft(), ()):
            if cell not in reached:
                reached.add(cell)
                queue.append(cell)
    return frozenset(reached)


def native_area_birth_source(fight, cell):
    """An actual selected Qq pointer can authorize an explicit non-ground birth.

    The dispatcher owns this transient scope across ordered area removal and
    birth siblings. Merely finding an arbitrary glyph at a cell is insufficient.
    No actor/breed/effect/map IDs grant this exception.
    """
    from .combat_state_managers import _area_pv_scopes, registered_area_pv

    for owner, row in reversed(_area_pv_scopes.get()):
        if owner is fight and tuple(row.get("cell", ())) == tuple(cell):
            pv = registered_area_pv(fight, row.get("uid"))
            if pv is not None and pv.position == tuple(cell):
                return True
    return False


def require_ground_birth(fight, cell):
    if not fight_supported(fight, cell) and not native_area_birth_source(fight, cell):
        raise ValueError("Ordinary ground birth requires a qualified combat floor")
