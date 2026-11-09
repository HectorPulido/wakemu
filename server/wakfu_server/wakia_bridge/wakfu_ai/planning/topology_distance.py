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


@lru_cache(maxsize=16)
def _immutable_adjacencies(edges, cells):
    forward, reverse = directed_adjacencies(edges, cells=cells)
    return tuple(
        MappingProxyType(
            {cell: frozenset(neighbors) for cell, neighbors in direction.items()}
        )
        for direction in (forward, reverse)
    )


def immutable_directed_adjacencies(edges, *, cells):
    """Reuse read-only adjacency for an exact complete terrain snapshot.

    Mutable inputs are reread by value every time, never cached by identity.
    Live occupancy, actor state, hazards and movement budgets are deliberately
    absent: callers derive those dynamic facts freshly from each native state.
    All XYZ cells and directed edges participate in the bounded cache key.
    """
    check()
    frozen_cells = []
    for index, cell in enumerate(cells):
        if index % 1024 == 0:
            check()
        frozen_cells.append(tuple(cell))
    frozen_edges = []
    for index, (start, end) in enumerate(edges):
        if index % 1024 == 0:
            check()
        frozen_edges.append((tuple(start), tuple(end)))
    result = _immutable_adjacencies(frozenset(frozen_edges), frozenset(frozen_cells))
    check()
    return result


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


def _measure(cells, edges, actors, *, actor_id=None):
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
        return dict(
            topologyDistances=None,
            allyRelaxedTopologyDistances=None,
            topologyCellCount=len(cells),
            **extra
        )
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
    # Navigation can look beyond a teammate occupying a corridor. These
    # separate facts never certify that the actor can walk through that cell.
    # Derive one complete reverse field per affiliation, not one per actor.
    relaxed, relaxed_primary = {}, {}
    for team in {actor["team"] for actor in live}:
        check()
        friendly = [actor for actor in live if actor["team"] == team]
        enemy_cells = {
            tuple(actor["position"]) for actor in live if actor["team"] != team
        }
        if not enemy_cells:
            relaxed.update((str(actor["id"]), 0) for actor in friendly)
            continue
        friendly_cells = {tuple(actor["position"]) for actor in friendly}
        field = _field(reverse, enemy_cells, occupied - enemy_cells - friendly_cells)
        for actor in friendly:
            relaxed[str(actor["id"])] = field.get(tuple(actor["position"]))
        primary_cells = {
            tuple(actor["position"])
            for actor in live
            if actor["team"] != team and actor.get("registeredSummon") is not True
        }
        if primary_cells and primary_cells != enemy_cells:
            # A hostile summon is still a blocker when the goal is its owner.
            # Only friendly occupancy is relaxed; terrain and hostile occupancy
            # retain the same exact directed XYZ authority as the strict facts.
            primary_field = _field(reverse, primary_cells, enemy_cells - primary_cells)
            for actor in friendly:
                relaxed_primary[str(actor["id"])] = primary_field.get(
                    tuple(actor["position"])
                )
    extra["allyRelaxedTopologyDistances"] = relaxed
    if relaxed_primary:
        extra["allyRelaxedPrimaryTopologyDistances"] = relaxed_primary
    return dict(topologyDistances=result, topologyCellCount=len(cells), **extra)


@lru_cache(maxsize=128)
def _immutable_measure(cells, edges, actors, actor_id):
    # HP magnitude does not affect topology: only live occupancy and whether
    # an ally needs healing matter. Keep team, XYZ and summon identity exact.
    return _measure(
        cells,
        edges,
        [
            dict(
                id=identity,
                team=team,
                position=position,
                hp=1,
                max_hp=2 if wounded else 1,
                registeredSummon=summon,
            )
            for identity, team, position, wounded, summon in actors
        ],
        actor_id=actor_id,
    )


def measure(cells, edges, actors, *, actor_id=None):
    """Reuse topology facts only across exactly equivalent immutable states."""
    check()
    try:
        from wakfu_server.combat_geometry_snapshot import ImmutableTerrainSet
    except ImportError:
        return _measure(cells, edges, actors, actor_id=actor_id)
    if type(edges) is not ImmutableTerrainSet or type(cells) is not ImmutableTerrainSet:
        return _measure(cells, edges, actors, actor_id=actor_id)
    live = [actor for actor in actors if actor["hp"] > 0]
    source = next((actor for actor in live if actor["id"] == actor_id), None)
    descriptors = tuple(
        (
            actor["id"],
            actor["team"],
            tuple(actor["position"]),
            source is not None
            and actor["id"] != source["id"]
            and actor["team"] == source["team"]
            and actor["hp"] < actor["max_hp"],
            actor.get("registeredSummon") is True,
        )
        for actor in live
    )
    cached = _immutable_measure(cells, edges, descriptors, actor_id)
    check()
    # The cache owns its dictionaries. Callers may enrich or mutate public
    # facts without poisoning subsequent previews or another fight.
    result = dict(cached)
    for name in (
        "topologyDistances",
        "primaryTopologyDistances",
        "allyRelaxedTopologyDistances",
        "allyRelaxedPrimaryTopologyDistances",
    ):
        if isinstance(result.get(name), dict):
            result[name] = dict(result[name])
    if "nativeSupportApproach" in result:
        support = dict(result["nativeSupportApproach"])
        support["targetIds"] = list(support["targetIds"])
        result["nativeSupportApproach"] = support
    return result
