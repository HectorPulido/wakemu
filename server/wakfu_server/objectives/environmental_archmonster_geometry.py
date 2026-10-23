"""Read-only single native archmonster placement in an occupied exact region.

The caller owns group-registry, event-scope and map-population locks, actor UID
allocation and actual construction. This helper neither admits an event nor
changes its immutable source population count.
"""
from . import environmental_presence as presence
from . import environmental_storage as storage
from .environmental_runtime import integer


def plan_geometry(db, map_id, instance_id, region_id, breed, level, *, taken):
    """Return one deterministic native (x,y,z), or None when unavailable.

    ``taken`` contains additional occupied XY pairs. All scene populations,
    pending growth reservations and native actor footprints are checked afresh.
    Population caps come from the existing declared random-roster policy; its
    multi-member sizing and scenario/objective bindings are not used here.
    """
    for value, label in (
        (map_id, "archmonster map"),
        (region_id, "archmonster region"),
        (breed, "archmonster breed"),
        (level, "archmonster level"),
    ):
        integer(value, label, minimum=1)
    integer(instance_id, "archmonster world instance")
    if (
        map_id >= 2**31
        or region_id >= 2**31
        or breed >= 2**31
        or level >= 2**15
    ):
        raise ValueError("Invalid native archmonster geometry identity")
    blocked = set()
    for point in taken:
        if (
            not isinstance(point, (tuple, list))
            or len(point) != 2
            or any(
                type(axis) is not int or not -(2**31) <= axis < 2**31
                for axis in point
            )
        ):
            raise ValueError("Invalid additional archmonster occupied cell")
        blocked.add(tuple(point))
    occupied = presence.capture(map_id, instance_id)
    if occupied is None:
        return None
    storage._transaction(db)
    from .environmental_random_rosters import CONTRACT, _digest, _geometry, _scene_cells
    from wakfu_server import native_catalog
    from wakfu_server.combat_actor_snapshot import native_actor_catalog
    from wakfu_server.combat_obstacle_condition import footprint
    from wakfu_server.monster_population_capacity import (
        physical_groups,
        pending_growth_groups,
    )
    from wakfu_server.monsters import statistics

    policy = db.execute(
        "SELECT v.policy_contract,v.max_zone_groups,v.max_zone_members "
        "FROM environmental_random_roster_active a "
        "JOIN environmental_random_roster_versions v USING(policy_version) WHERE a.singleton",
    ).fetchone()
    if (
        policy is None
        or policy["policy_contract"] != CONTRACT
        or any(
            type(policy[key]) is not int or policy[key] <= 0
            for key in ("max_zone_groups", "max_zone_members")
        )
    ):
        raise ValueError("Missing authoritative archmonster population capacity policy")
    groups = physical_groups(db, map_id, instance_id)
    pending = pending_growth_groups(
        db,
        map_id,
        instance_id,
        existing_group_ids={group["group_id"] for group in groups},
    )
    population = [*groups, *pending]
    if (
        len(population) + 1 > policy["max_zone_groups"]
        or sum(len(group["members"]) for group in population) + 1
        > policy["max_zone_members"]
    ):
        return None
    if statistics(breed, level)["HP"] <= 0:
        raise ValueError("Native archmonster cannot initialize a living actor")
    revision = native_catalog.release()
    profiles = native_actor_catalog()["npc_profiles"]
    radius = profiles[str(breed)]["physical_radius"]
    for group in population:
        for member in group["members"]:
            blocked.update(
                footprint(
                    (member["x"], member["y"]),
                    profiles[str(member["ref"])]["physical_radius"],
                )
            )
    blocked.update(_scene_cells(db, map_id, instance_id))
    blocked.update(
        (row["x"], row["y"])
        for row in db.execute(
            "SELECT x,y FROM planted_resources WHERE map_id=%s AND instance_id=%s",
            (map_id, instance_id),
        ).fetchall()
    )
    for table in ("mining_vein_slots", "fishing_spot_slots"):
        blocked.update(
            (row["x"], row["y"])
            for row in db.execute(
                f"SELECT x,y FROM {table} WHERE map_id=%s AND instance_id=%s AND enabled",
                (map_id, instance_id),
            ).fetchall()
        )
    world = occupied[0]
    with world.lock:
        blocked.update(
            (row["x"], row["y"])
            for _, _, row in world.players.values()
            if world.location(row) == (map_id, instance_id)
        )
    positions, adjacency = _geometry(revision, map_id, region_id)
    candidates = sorted(
        (point for point in positions if adjacency[point]),
        key=lambda point: _digest(
            [map_id, instance_id, region_id, breed, level, point]
        ),
    )
    for point in candidates:
        cells = footprint(point[:2], radius)
        if not blocked.intersection(cells) and all(
            (x, y, point[2]) in adjacency for x, y in cells
        ):
            if native_catalog.release() != revision:
                raise ValueError(
                    "Native archmonster terrain source changed during placement"
                )
            return point if presence.current(occupied, map_id, instance_id) else None
    return None
