"""Explicit local wandering policy over verified native directed walk edges.

One bounded group path per attempt; never invent cells or heights.
Caller snapshots online players and excludes fighting/harvesting positions.
PersistentGroups owns PostgreSQL CAS movement; no memory fallback.
"""
import random
import struct
import math
from copy import deepcopy
from protocol_codec import DIRECTIONS


def point(actor):
    return tuple(actor[k] for k in ("x", "y", "z"))


def visible_groups(groups, players, *, radius, tick, batch_size):
    """Rotate eligible visible groups before spending native pathfinding time."""
    nearby = [
        group
        for group in groups
        if group["status"] == "available"
        and any(
            max(abs(member["x"] - player["x"]), abs(member["y"] - player["y"]))
            <= radius
            for member in group["members"]
            for player in players
        )
    ]
    if not nearby:
        return []
    start = (tick * batch_size) % len(nearby)
    return nearby[start:] + nearby[:start]


def movement_packet(actor_id, origin, destination):
    dx, dy, dz = tuple(b - a for a, b in zip(origin, destination))
    direction = next(
        (d for d, (_, x, y) in DIRECTIONS.items() if (x, y) == (dx, dy)), None
    )
    if actor_id >= 0 or direction is None or not -16 <= dz <= 15:
        raise ValueError("Invalid native NPC step")
    # csR13852: i64actor + aAT(i32x,i32y,i16z,u8steps,packed delta).
    return 13852, struct.pack(
        ">qiihBB", actor_id, *origin, 1, (direction << 5) | (dz & 31)
    )


def edge_index(valid_edges):
    edges = frozenset((tuple(a), tuple(b)) for a, b in valid_edges)
    adjacent = {}
    for origin, destination in edges:
        adjacent.setdefault(origin, []).append(destination)
    return edges, adjacent


def policy(store):
    with store.connection() as db:
        row = db.execute(
            "SELECT value FROM settings WHERE name='monster_wander'"
        ).fetchone()
    value = row["value"] if row is not None else None
    if not isinstance(value, dict) or set(value) != {
        "interval_seconds",
        "move_probability",
        "min_steps",
        "max_steps",
        "radius",
    }:
        raise ValueError("Invalid monster wander policy")
    for key in ("interval_seconds", "move_probability"):
        if type(value[key]) not in (int, float) or not math.isfinite(value[key]):
            raise ValueError("Invalid monster wander timing or probability")
    if (
        not 0 < value["interval_seconds"] <= 3600
        or not 0 <= value["move_probability"] <= 1
    ):
        raise ValueError("Invalid monster wander timing or probability")
    if (
        any(type(value[key]) is not int for key in ("min_steps", "max_steps", "radius"))
        or not 1 <= value["min_steps"] <= value["max_steps"] <= 255
        or not 1 <= value["radius"] <= 1000
    ):
        raise ValueError("Invalid monster wander distance")
    return value


def plan(
    members,
    players,
    valid_edges,
    *,
    occupied=(),
    radius=20,
    rng=None,
    indexed=None,
    destination_allowed=None,
):
    if not members or radius <= 0:
        return None
    origins = [point(m) for m in members]
    if not any(
        max(abs(p["x"] - o[0]), abs(p["y"] - o[1])) <= radius
        for p in players
        for o in origins
    ):
        return None
    blocked = set(occupied) | {point(p) for p in players}
    edges, adjacent = edge_index(valid_edges) if indexed is None else indexed
    candidates = []
    for b in adjacent.get(origins[0], ()):
        a = origins[0]
        delta = tuple(y - x for x, y in zip(a, b))
        destinations = [tuple(x + d for x, d in zip(o, delta)) for o in origins]
        if len(set(destinations)) != len(destinations) or any(
            d in blocked for d in destinations
        ):
            continue
        if destination_allowed is not None and any(
            not destination_allowed(destination) for destination in destinations
        ):
            continue
        if any((o, d) not in edges for o, d in zip(origins, destinations)):
            continue
        try:
            packets = [
                movement_packet(m["id"], o, d)
                for m, o, d in zip(members, origins, destinations)
            ]
        except ValueError:
            continue
        moved = deepcopy(list(members))
        for m, d in zip(moved, destinations):
            m.update(zip(("x", "y", "z"), d))
        candidates.append(dict(members=moved, packets=packets))
    return (rng or random).choice(candidates) if candidates else None


def plan_path(
    members,
    players,
    valid_edges,
    *,
    occupied=(),
    radius=20,
    min_steps=1,
    max_steps=3,
    rng=None,
    indexed=None,
    destination_allowed=None,
):
    rng = rng or random
    indexed = edge_index(valid_edges) if indexed is None else indexed
    moved = members
    paths = [[point(member)] for member in members]
    base_occupied = set(occupied)
    for _ in range(rng.randint(min_steps, max_steps)):
        # Do not let a multi-step wander path loop back through a cell it already
        # crossed. A short back-and-forth path looks stationary to the client.
        visited = {cell for path in paths for cell in path[:-1]}
        result = plan(
            moved,
            players,
            (),
            occupied=base_occupied | visited,
            radius=radius,
            rng=rng,
            indexed=indexed,
            destination_allowed=destination_allowed,
        )
        if result is None:
            break
        moved = result["members"]
        for path, member in zip(paths, moved):
            path.append(point(member))
    if moved is members:
        return None
    packets = []
    for member, path in zip(moved, paths):
        deltas = bytearray()
        for origin, destination in zip(path, path[1:]):
            deltas.extend(movement_packet(member["id"], origin, destination)[1][-1:])
        packets.append(
            (13852, struct.pack(">qiihB", member["id"], *path[0], len(deltas)) + deltas)
        )
    return dict(members=moved, packets=packets)


def wander_location(
    groups,
    map_id,
    instance_id,
    players,
    valid_edges,
    emit,
    *,
    occupied=(),
    radius=20,
    rng=None,
    excluded_ids=(),
    move_probability=0.25,
    min_steps=1,
    max_steps=3,
    indexed=None,
):
    """Serialize claim/move/broadcast using the same registry lock.

    emit(opcode,body) targets this map/instance; no session sender needed.
    Call at an explicit few-second interval, not on every server idle tick.
    """
    players = [
        p for p in players if (p["map_id"], p["instance_id"]) == (map_id, instance_id)
    ]
    if not players:
        return []
    from .monster_habitat_cells import habitat_destination_allowed

    rng = rng or random
    indexed = edge_index(valid_edges) if indexed is None else indexed
    moved_keys = []
    with groups.lock:
        local = groups.snapshot(map_id, instance_id)
        roster = sorted(
            (group for group in local if group["status"] == "available"),
            key=lambda group: group["key"],
        )
        blocked = set(occupied)
        blocked.update(
            point(member)
            for group in local
            for member in group["members"]
            if group["status"] == "fighting" or member["id"] in excluded_ids
        )
        for group in roster:
            candidate = deepcopy(list(group["members"]))
            packets = []
            for index, member in enumerate(candidate):
                if member["id"] in excluded_ids or rng.random() >= move_probability:
                    continue
                others = {
                    point(other)
                    for other_group in roster
                    for other in (
                        candidate
                        if other_group["key"] == group["key"]
                        else other_group["members"]
                    )
                    if other["id"] != member["id"]
                }
                result = plan_path(
                    [member],
                    players,
                    valid_edges,
                    occupied=blocked | others,
                    radius=radius,
                    rng=rng,
                    indexed=indexed,
                    min_steps=min_steps,
                    max_steps=max_steps,
                    destination_allowed=lambda cell: habitat_destination_allowed(
                        map_id, instance_id, cell
                    ),
                )
                if result is not None:
                    candidate[index] = result["members"][0]
                    packets.extend(result["packets"])
            if not packets or not groups.move_members(
                group["key"], group["members"], candidate
            ):
                continue
            group["members"] = candidate
            for packet in packets:
                emit(*packet)
            moved_keys.append(group["key"])
    return moved_keys
