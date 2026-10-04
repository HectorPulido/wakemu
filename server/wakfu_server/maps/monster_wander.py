"""Explicit local wandering policy over verified native directed walk edges.

One short group translation per callback; never invent cells or heights.
Caller snapshots online players and excludes fighting/harvesting positions.
Only RedisGroups exposes durable CAS movement; no memory fallback.
"""
import random
import struct
from copy import deepcopy
from protocol_codec import DIRECTIONS


def point(actor):
    return tuple(actor[k] for k in ("x", "y", "z"))


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


def plan(members, players, valid_edges, *, occupied=(), radius=20, rng=None):
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
    edges = set((tuple(a), tuple(b)) for a, b in valid_edges)
    candidates = []
    for a, b in edges:
        if a != origins[0]:
            continue
        delta = tuple(y - x for x, y in zip(a, b))
        destinations = [tuple(x + d for x, d in zip(o, delta)) for o in origins]
        if len(set(destinations)) != len(destinations) or any(
            d in blocked for d in destinations
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
    excluded_ids=()
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
    moved_keys = []
    with groups.lock:
        roster = groups.available(map_id, instance_id)
        blocked = set(occupied)
        for group in roster:
            if any(m["id"] in excluded_ids for m in group["members"]):
                continue
            others = {
                point(m)
                for g in roster
                if g["key"] != group["key"]
                for m in g["members"]
            }
            result = plan(
                group["members"],
                players,
                valid_edges,
                occupied=blocked | others,
                radius=radius,
                rng=rng,
            )
            if result is None or not groups.move_members(
                group["key"], group["members"], result["members"]
            ):
                continue
            group["members"] = result["members"]
            for packet in result["packets"]:
                emit(*packet)
            moved_keys.append(group["key"])
    return moved_keys
