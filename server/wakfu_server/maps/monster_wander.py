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


DISPERSION_RADIUS = 12


def group_neighbor_index(groups):
    """Index one leader per group once per map/instance planning batch."""
    buckets = {}
    for group in groups:
        if group["members"]:
            cell = point(group["members"][0])
            buckets.setdefault(
                (cell[0] // DISPERSION_RADIUS, cell[1] // DISPERSION_RADIUS), []
            ).append(cell)
    return buckets


def nearest_group(origin, buckets):
    bx, by = origin[0] // DISPERSION_RADIUS, origin[1] // DISPERSION_RADIUS
    candidates = (
        cell
        for x in range(bx - 1, bx + 2)
        for y in range(by - 1, by + 2)
        for cell in buckets.get((x, y), ())
        if cell != origin
        and max(abs(cell[0] - origin[0]), abs(cell[1] - origin[1])) <= DISPERSION_RADIUS
    )
    return min(
        candidates,
        key=lambda cell: (cell[0] - origin[0]) ** 2 + (cell[1] - origin[1]) ** 2,
        default=None,
    )


def choose_step(candidates, rng, away_from=None, origin=None):
    if not candidates:
        return None
    if away_from is not None:

        def distance(cell):
            return (cell[0] - away_from[0]) ** 2 + (cell[1] - away_from[1]) ** 2

        farther = [
            candidate
            for candidate in candidates
            if distance(point(candidate["members"][0])) > distance(origin)
        ]
        if farther:
            candidates = farther
    return rng.choice(candidates)


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
    away_from=None,
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
    return choose_step(candidates, rng or random, away_from, origins[0])


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
    away_from=None,
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
            away_from=away_from,
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


COHESION_RADIUS = 4


def _flexible_group_step(members, players, indexed, options):
    """Try the leader's directions once, letting blocked companions hold.

    This bounded fallback keeps a crowded formation from becoming a permanent
    wall. It adds no actor path searches or independent movement decisions.
    """
    edges, adjacent = indexed
    origins = [point(member) for member in members]
    blocked = set(options.get("occupied", ()))
    blocked.update(point(player) for player in players)
    # Conservatively disallow crossing an original companion cell, including
    # companions that might move: sequential client animations remain safe.
    blocked.update(origins)
    allowed = options.get("destination_allowed")
    candidates = []
    for leader_destination in adjacent.get(origins[0], ()):
        delta = tuple(b - a for a, b in zip(origins[0], leader_destination))
        destinations = []
        packets = []
        for member, origin in zip(members, origins):
            destination = tuple(a + b for a, b in zip(origin, delta))
            if (
                destination in blocked
                or (origin, destination) not in edges
                or (allowed is not None and not allowed(destination))
            ):
                destination = origin
            if destination != origin:
                try:
                    packets.append(movement_packet(member["id"], origin, destination))
                except ValueError:
                    destination = origin
            destinations.append(destination)
        if destinations[0] != leader_destination or not packets:
            continue
        if len(set(destinations)) != len(destinations) or any(
            max(
                abs(cell[0] - leader_destination[0]),
                abs(cell[1] - leader_destination[1]),
            )
            > COHESION_RADIUS
            for cell in destinations
        ):
            continue
        moved = deepcopy(list(members))
        for member, destination in zip(moved, destinations):
            member.update(zip(("x", "y", "z"), destination))
        candidates.append(dict(members=moved, packets=packets))
    return choose_step(
        candidates, options.get("rng") or random, options.get("away_from"), origins[0]
    )


def plan_group_path(members, players, valid_edges, **options):
    """Translate compact groups; safely draw distant companions to their leader.

    Regrouping holds the stable first roster member in place. Each follower uses
    a native directed edge that strictly reduces its distance; blocked routes
    wait for a later cadence rather than teleporting or detaching companions.
    """
    if not members or not players or options.get("radius", 20) <= 0:
        return None
    anchor = point(members[0])
    options = dict(options)
    neighbors = options.pop("neighbor_index", None)
    # Movement probability is decided by the caller BEFORE this conditional mix.
    if neighbors is not None and (options.get("rng") or random).random() < 0.5:
        options["away_from"] = nearest_group(anchor, neighbors)

    def distance(cell):
        return max(abs(cell[0] - anchor[0]), abs(cell[1] - anchor[1]))

    if all(distance(point(member)) <= COHESION_RADIUS for member in members):
        indexed = options.get("indexed")
        if indexed is None:
            indexed = edge_index(valid_edges)
        path_options = dict(options, indexed=indexed)
        result = plan_path(members, players, (), **path_options)
        if result is not None:
            return result
        if len(members) == 1:
            return None
        radius = options.get("radius", 20)
        if not any(
            max(abs(player["x"] - member["x"]), abs(player["y"] - member["y"]))
            <= radius
            for player in players
            for member in members
        ):
            return None
        return _flexible_group_step(members, players, indexed, options)
    radius = options.get("radius", 20)
    if not any(
        max(abs(player["x"] - member["x"]), abs(player["y"] - member["y"])) <= radius
        for player in players
        for member in members
    ):
        return None
    indexed = options.get("indexed")
    _, adjacent = edge_index(valid_edges) if indexed is None else indexed
    allowed = options.get("destination_allowed")
    occupied = set(options.get("occupied", ()))
    occupied.update(point(player) for player in players)
    occupied.update(point(member) for member in members)
    moved = deepcopy(list(members))
    packets = []
    for member in moved[1:]:
        origin = point(member)
        if distance(origin) <= COHESION_RADIUS:
            continue
        candidates = [
            destination
            for destination in adjacent.get(origin, ())
            if destination not in occupied
            and distance(destination) < distance(origin)
            and (allowed is None or allowed(destination))
        ]
        if not candidates:
            continue
        destination = min(candidates, key=lambda cell: (distance(cell), cell))
        try:
            packet = movement_packet(member["id"], origin, destination)
        except ValueError:
            continue
        occupied.remove(origin)
        occupied.add(destination)
        member.update(zip(("x", "y", "z"), destination))
        packets.append(packet)
    return dict(members=moved, packets=packets) if packets else None


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
    from wakfu_server.objectives.challenges import is_challenge_instance

    if is_challenge_instance(instance_id):
        return []
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
        neighbors = group_neighbor_index(local)
        for group in roster:
            members = list(group["members"])
            if not members or any(m["id"] in excluded_ids for m in members):
                continue
            if rng.random() >= move_probability:
                continue
            others = {
                point(member)
                for other_group in roster
                if other_group["key"] != group["key"]
                for member in other_group["members"]
            }
            result = plan_group_path(
                members,
                players,
                valid_edges,
                occupied=blocked | others,
                neighbor_index=neighbors,
                radius=radius,
                rng=rng,
                indexed=indexed,
                min_steps=min_steps,
                max_steps=max_steps,
                destination_allowed=lambda cell: habitat_destination_allowed(
                    map_id, instance_id, cell
                ),
            )
            if result is None:
                continue
            candidate = result["members"]
            packets = result["packets"]
            if not packets or not groups.move_members(
                group["key"], group["members"], candidate
            ):
                continue
            group["members"] = candidate
            for packet in packets:
                emit(*packet)
            moved_keys.append(group["key"])
    return moved_keys
