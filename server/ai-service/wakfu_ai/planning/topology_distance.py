"""Directed XYZ topology measurements, never a movement legality verdict."""
from collections import deque
import math
from functools import lru_cache
from types import MappingProxyType

from ..native.native_deadline import check


def _reverse(edges, cells=None):
    reverse = {}
    for index, (start, end) in enumerate(edges):
        if index % 1024 == 0:
            check()
        if cells is not None and (tuple(start) not in cells or tuple(end) not in cells):
            raise ValueError(
                "Native topology edge lies outside complete walkable cells"
            )
        reverse.setdefault(tuple(end), set()).add(tuple(start))
    return reverse


@lru_cache(maxsize=16)
def _immutable_reverse(edges, cells):
    # Only the derived adjacency is cached. Every XYZ cell/edge remains in
    # the complete native graph, and occupancy is recalculated per state.
    return MappingProxyType(
        {end: frozenset(starts) for end, starts in _reverse(edges, cells).items()}
    )


def _topology_reverse(edges, cells=None):
    check()
    try:
        from wakfu_server.combat_geometry_snapshot import ImmutableTerrainSet
    except ImportError:
        return _reverse(edges, cells)
    # Mutable/custom containers must be reread, even if their identity did
    # not change. The native frozen type validates integer tuples at creation.
    if type(edges) is ImmutableTerrainSet and type(cells) is ImmutableTerrainSet:
        result = _immutable_reverse(edges, cells)
        check()
        return result
    return _reverse(edges, cells)


def _field(reverse, enemies, blocked, *, until=None):
    distances = {cell: 0 for cell in enemies}
    queue = deque(sorted(enemies))
    visited = 0
    while queue and (until is None or until not in distances):
        if visited % 1024 == 0:
            check()
        visited += 1
        end = queue.popleft()
        for start in reverse.get(end, ()):
            if start not in blocked and start not in distances:
                distances[start] = distances[end] + 1
                queue.append(start)
    return distances


def distance_field(edges, enemies, blocked, *, cells=None):
    return _field(_topology_reverse(edges, cells), enemies, blocked)


def directed_adjacencies(edges, *, cells=None):
    """Build both directions from the complete edge list in one traversal."""
    forward, reverse = {}, {}
    for index, (start, end) in enumerate(edges):
        if index % 1024 == 0:
            check()
        start, end = tuple(start), tuple(end)
        if cells is not None and (start not in cells or end not in cells):
            raise ValueError(
                "Native topology edge lies outside complete walkable cells"
            )
        forward.setdefault(start, set()).add(end)
        reverse.setdefault(end, set()).add(start)
    check()
    return forward, reverse


def distance_field_from_reverse(reverse, goals, blocked):
    """Measure fresh occupancy and goals using an already derived adjacency."""
    check()
    result = _field(reverse, goals, blocked)
    check()
    return result


def minimum_exposure(reverse, goals, blocked, origin, hazards):
    """Count unavoidable hazardous entries on a directed, occupied graph.

    This is a navigation preference only; native previews still decide
    movement legality and apply the actual glyph effects.
    """
    return exposure_field_from_reverse(
        reverse, goals, blocked, hazards, until=origin
    ).get(origin)


def exposure_field_from_reverse(reverse, goals, blocked, hazards, *, until=None):
    """Minimum hazardous entries, retaining direction and occupied cells."""
    distances = {cell: 0 for cell in goals}
    pending = deque(sorted(goals))
    visited = 0
    while pending:
        if visited % 1024 == 0:
            check()
        visited += 1
        end = pending.popleft()
        if end == until:
            break
        cost = int(end in hazards)
        for start in reverse.get(end, ()):
            if start in blocked:
                continue
            candidate = distances[end] + cost
            if candidate < distances.get(start, math.inf):
                distances[start] = candidate
                if cost:
                    pending.append(start)
                else:
                    pending.appendleft(start)
    return distances


def measure(cells, edges, actors, *, actor_id=None):
    live = [actor for actor in actors if actor["hp"] > 0]
    source = next((actor for actor in live if actor["id"] == actor_id), None)
    allies = [
        actor
        for actor in live
        if source is not None
        and actor["id"] != source["id"]
        and actor["team"] == source["team"]
        and actor["hp"] < actor["max_hp"]
    ]
    support = dict(
        actorId=actor_id,
        targetIds=sorted(actor["id"] for actor in allies),
        distance=None,
    )
    extra = dict(nativeSupportApproach=support) if actor_id is not None else {}
    if edges is None:
        return dict(topologyDistances=None, topologyCellCount=len(cells), **extra)
    reverse = _topology_reverse(edges, cells)
    occupied = {tuple(actor["position"]) for actor in live}
    if source is not None and allies:
        origin = tuple(source["position"])
        goals = {tuple(actor["position"]) for actor in allies}
        support["distance"] = _field(
            reverse, goals, occupied - goals - {origin}, until=origin
        ).get(origin)
    result = {}
    primary_result = {}
    for actor in live:
        origin = tuple(actor["position"])
        enemies = {
            tuple(other["position"]) for other in live if other["team"] != actor["team"]
        }
        if not enemies:
            result[str(actor["id"])] = 0
            continue
        blocked = occupied - enemies - {origin}
        distances = _field(reverse, enemies, blocked, until=origin)
        result[str(actor["id"])] = distances.get(origin)
        primary_enemies = {
            tuple(other["position"])
            for other in live
            if other["team"] != actor["team"]
            and other.get("registeredSummon") is not True
        }
        if primary_enemies and primary_enemies != enemies:
            primary_blocked = occupied - primary_enemies - {origin}
            primary_distances = _field(
                reverse, primary_enemies, primary_blocked, until=origin
            )
            primary_result[str(actor["id"])] = primary_distances.get(origin)
    if primary_result:
        extra["primaryTopologyDistances"] = primary_result
    return dict(topologyDistances=result, topologyCellCount=len(cells), **extra)
