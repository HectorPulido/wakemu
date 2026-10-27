"""Event-frozen random proportions from exact original environmental species.

Ordinary ecology's declared sizing policy is pinned in normalized SQL. Neither
zone families nor challenge/player levels supply extra species or actor levels.
"""
from collections import defaultdict, deque
from functools import lru_cache
from hashlib import sha256
import json
import struct

from . import environmental_storage as storage

CONTRACT = "wakemu.exact-species-random-roster.v1"


def binding(db, event):
    """Match an immutable event profile to an exact original scenario location."""
    storage._transaction(db)
    frozen = db.execute(
        "SELECT source_key,scenario_id,policy_version FROM environmental_random_roster_draws WHERE instance_id=%s",
        (event["instance_id"],),
    ).fetchone()
    source = (
        (
            "JOIN environmental_random_roster_draws d USING(source_key,scenario_id,policy_version) "
            "WHERE d.instance_id=%s"
        )
        if frozen is not None
        else (
            "JOIN environmental_random_roster_active a USING(policy_version) WHERE a.singleton AND a.enabled"
        )
    )
    parameters = (event["instance_id"],) if frozen is not None else ()
    rows = db.execute(
        "SELECT p.*,v.min_members,v.max_members,v.max_zone_members,v.max_zone_groups,v.policy_contract "
        "FROM environmental_random_roster_policies p JOIN environmental_random_roster_versions v USING(policy_version) "
        "JOIN environmental_random_roster_bindings b USING(source_key,scenario_id,policy_version) "
        "JOIN environmental_runtime_profiles r ON r.profile_key=%s AND r.version=%s "
        + source
        + " AND p.scenario_id=r.native_scenario_id AND b.map_id=%s AND b.region_id=%s",
        (
            event["profile_key"],
            event["version"],
            *parameters,
            event["map_id"],
            event["region_id"],
        ),
    ).fetchall()
    if frozen is not None and not rows:
        raise ValueError("Frozen environmental draw lost its original scope/source")
    if len(rows) > 1:
        raise ValueError("Ambiguous environmental random roster source")
    return None if not rows else dict(rows[0])


def _digest(value):
    return sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _sample(seed, label, size):
    """Stable unbiased independent draw; proportions are never forced equal."""
    limit = (1 << 256) // size * size
    counter = 0
    while True:
        value = int(sha256(f"{seed}:{label}:{counter}".encode()).hexdigest(), 16)
        if value < limit:
            return value % size
        counter += 1


def draw_slots(seed, group_count, minimum, maximum, species):
    """Pure draw over exact {reference:native minimum level} source facts."""
    if (
        type(seed) is not str
        or len(seed) != 64
        or any(c not in "0123456789abcdef" for c in seed)
        or type(species) is not dict
        or not species
        or any(
            type(r) is not int
            or r <= 0
            or type(level) is not int
            or not 1 <= level <= 32767
            for r, level in species.items()
        )
        or type(minimum) is not int
        or type(maximum) is not int
        or not 2 <= minimum <= maximum <= 8
        or type(group_count) is not int
        or not 0 < group_count <= 4096
    ):
        raise ValueError("Invalid frozen environmental roster draw")
    refs = sorted(species)
    result = []
    for ordinal in range(group_count):
        count = minimum + _sample(seed, f"group:{ordinal}:size", maximum - minimum + 1)
        for member in range(count):
            reference = refs[
                _sample(seed, f"group:{ordinal}:member:{member}", len(refs))
            ]
            result.append(
                dict(
                    group_ordinal=ordinal,
                    member_ordinal=member,
                    monster_reference=reference,
                    native_level=species[reference],
                )
            )
    if len(result) > 4096:
        raise ValueError("Environmental roster exceeds bounded actor population")
    return result


def _draw(db, event, policy, species):
    identity = [
        event["instance_id"],
        event["profile_key"],
        event["version"],
        policy["source_key"],
        policy["scenario_id"],
        policy["policy_version"],
    ]
    seed = _digest(identity)
    expected = draw_slots(
        seed,
        policy["group_count"],
        policy["min_members"],
        policy["max_members"],
        species,
    )
    digest = _digest(expected)
    previous = db.execute(
        "SELECT * FROM environmental_random_roster_draws WHERE instance_id=%s",
        (event["instance_id"],),
    ).fetchone()
    facts = dict(
        source_key=policy["source_key"],
        scenario_id=policy["scenario_id"],
        policy_version=policy["policy_version"],
        seed_sha256=seed,
        group_count=policy["group_count"],
        min_members=policy["min_members"],
        max_members=policy["max_members"],
        roster_sha256=digest,
    )
    if previous is None:
        db.execute(
            "INSERT INTO environmental_random_roster_draws VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                event["instance_id"],
                *[
                    facts[k]
                    for k in (
                        "source_key",
                        "scenario_id",
                        "policy_version",
                        "seed_sha256",
                        "group_count",
                        "min_members",
                        "max_members",
                        "roster_sha256",
                    )
                ],
            ),
        )
        for row in expected:
            db.execute(
                "INSERT INTO environmental_random_roster_slots VALUES(%s,%s,%s,%s,%s)",
                (
                    event["instance_id"],
                    row["group_ordinal"],
                    row["member_ordinal"],
                    row["monster_reference"],
                    row["native_level"],
                ),
            )
    else:
        if any(previous[k] != value for k, value in facts.items()):
            raise ValueError("Frozen environmental draw policy or source changed")
        actual = db.execute(
            "SELECT group_ordinal,member_ordinal,monster_reference,native_level "
            "FROM environmental_random_roster_slots WHERE instance_id=%s ORDER BY group_ordinal,member_ordinal",
            (event["instance_id"],),
        ).fetchall()
        if [dict(r) for r in actual] != expected:
            raise ValueError("Frozen environmental draw members changed")
    return seed, expected


def frozen_birth_count(db, event, entity_kind):
    """Read the complete immutable draw for a bound collaborative objective.

    No draw means no born population yet, never a zero completion target.
    """
    if entity_kind not in ("group", "monster"):
        raise ValueError("Unsupported environmental frozen population kind")
    row = db.execute(
        "SELECT * FROM environmental_random_roster_draws WHERE instance_id=%s",
        (event["instance_id"],),
    ).fetchone()
    if row is None:
        return None
    actual = db.execute(
        """SELECT e.profile_key,e.version,e.map_id,e.world_instance_id,e.region_id,
        r.native_scenario_id,r.mode,p.native_mode,p.group_count AS source_group_count,
        v.min_members AS source_min_members,v.max_members AS source_max_members,v.policy_contract
        FROM environmental_event_instances e JOIN environmental_runtime_profiles r
          ON r.profile_key=e.profile_key AND r.version=e.version
        JOIN environmental_random_roster_policies p ON p.source_key=%s AND p.scenario_id=%s AND p.policy_version=%s
        JOIN environmental_random_roster_versions v USING(policy_version)
        JOIN environmental_random_roster_bindings b ON b.source_key=p.source_key AND b.scenario_id=p.scenario_id
          AND b.policy_version=p.policy_version AND b.map_id=e.map_id AND b.region_id=e.region_id
        WHERE e.instance_id=%s AND r.native_scenario_id=p.scenario_id""",
        (
            row["source_key"],
            row["scenario_id"],
            row["policy_version"],
            event["instance_id"],
        ),
    ).fetchone()
    if (
        actual is None
        or actual["policy_contract"] != CONTRACT
        or actual["mode"] != actual["native_mode"].lower()
        or row["group_count"] != actual["source_group_count"]
        or row["min_members"] != actual["source_min_members"]
        or row["max_members"] != actual["source_max_members"]
        or any(
            event[key] != actual[key]
            for key in (
                "profile_key",
                "version",
                "map_id",
                "world_instance_id",
                "region_id",
            )
            if key in event
        )
    ):
        raise ValueError("Frozen environmental birth source or profile changed")
    identity = [
        event["instance_id"],
        actual["profile_key"],
        actual["version"],
        row["source_key"],
        row["scenario_id"],
        row["policy_version"],
    ]
    if row["seed_sha256"] != _digest(identity):
        raise ValueError("Frozen environmental draw identity changed")
    slots = [
        dict(r)
        for r in db.execute(
            "SELECT group_ordinal,member_ordinal,monster_reference,native_level "
            "FROM environmental_random_roster_slots WHERE instance_id=%s ORDER BY group_ordinal,member_ordinal",
            (event["instance_id"],),
        ).fetchall()
    ]
    groups = defaultdict(list)
    for slot in slots:
        groups[slot["group_ordinal"]].append(slot)
    if (
        not slots
        or len(slots) > 4096
        or _digest(slots) != row["roster_sha256"]
        or sorted(groups) != list(range(row["group_count"]))
        or any(
            not row["min_members"] <= len(members) <= row["max_members"]
            or [m["member_ordinal"] for m in members] != list(range(len(members)))
            for members in groups.values()
        )
    ):
        raise ValueError("Frozen environmental birth roster digest or ordinals changed")
    species = {
        r["monster_reference"]: r["native_min_level"]
        for r in db.execute(
            "SELECT s.monster_reference,n.native_min_level FROM environmental_random_roster_species s "
            "JOIN environmental_random_native_species n USING(monster_reference) "
            "WHERE s.source_key=%s AND s.scenario_id=%s AND s.policy_version=%s",
            (row["source_key"], row["scenario_id"], row["policy_version"]),
        ).fetchall()
    }
    if any(
        species.get(slot["monster_reference"]) != slot["native_level"] for slot in slots
    ):
        raise ValueError("Frozen environmental birth species or native level changed")
    return row["group_count"] if entity_kind == "group" else len(slots)


@lru_cache(maxsize=64)
def _geometry(revision, map_id, region_id):
    """Use ordinary planner's exact region/walkmesh and bidirectional edges."""
    from wakfu_server.planting_cells import cells
    from wakfu_server.combat_terrain import map_geometry

    surfaces = {
        (x, y, row["z"])
        for (x, y), rows in cells(map_id).items()
        for row in rows
        if row["region_id"] == region_id
    }
    geometry = map_geometry(map_id)
    positions = surfaces.intersection(tuple(p) for p in geometry["cells"])
    edges = {(tuple(a), tuple(b)) for a, b in geometry.get("edges", ())}
    adjacency = {point: [] for point in positions}
    for start, end in edges:
        if start in positions and end in positions and (end, start) in edges:
            adjacency[start].append(end)
    return tuple(sorted(positions)), {p: tuple(sorted(v)) for p, v in adjacency.items()}


def _scene_cells(db, map_id, instance_id):
    """Respect the same enabled NPCs and installed interactive scene geometry."""
    from wakfu_server import npc_world, npc_placements, world_static
    from wakfu_server.native_interactive_components import components

    result = {
        (r["x"], r["y"])
        for r in (
            *npc_world.load_scene(db, map_id, instance_id),
            *npc_placements.load_scene(db, map_id, instance_id),
        )
    }
    for row in world_static.objects(map_id):
        result.add((row["x"], row["y"]))
        body = components(bytes.fromhex(row["payload_hex"])).get(1)
        if body is None:
            continue
        if len(body) < 23:
            raise ValueError("Truncated original interactive footprint")
        count = struct.unpack_from(">h", body, 19)[0]
        if count < 0 or 21 + count * 10 + 2 > len(body):
            raise ValueError("Invalid original interactive footprint count")
        anchor_x, anchor_y, _ = struct.unpack_from(">iih", body, 2)
        result.add((anchor_x, anchor_y))
        # Original bEH reads exactly count extra absolute XYZ triples.
        for index in range(count):
            x, y, z = struct.unpack_from(">iih", body, 21 + index * 10)
            result.add((x, y))
    return result


def plan(db, event, profile, policy, *, taken):
    """Persist all source draws once, then propose the full available population.

    A lack of placement/capacity returns no spawn; already persisted composition
    remains unchanged for the next occupied retry. Caller owns scope/map locks.
    """
    storage._transaction(db)
    from wakfu_server import native_catalog
    from wakfu_server.monster_population_capacity import (
        physical_groups,
        pending_growth_groups,
        physical_cells,
    )
    from wakfu_server.combat_actor_snapshot import native_actor_catalog
    from wakfu_server.combat_obstacle_condition import footprint

    expected_family = (
        "monster_destroy"
        if policy["native_type"] == 5
        else "group_defeat"
        if policy["native_type"] == 7
        else "monster_defeat"
    )
    if (
        policy["policy_contract"] != CONTRACT
        or profile["native_scenario_id"] != policy["scenario_id"]
        or profile["family"] != expected_family
        or profile["mode"] != policy["native_mode"].lower()
        or profile["duration_ms"] != policy["duration_ms"]
        or profile["level_min"] != max(1, policy["challenge_level_min"])
        or profile["level_max"] != policy["challenge_level_max"]
    ):
        raise ValueError("Environmental random roster differs from original profile")
    objectives = storage._objectives(db, profile)
    threshold = (
        policy["nb_group_for_reward"]
        if expected_family == "group_defeat"
        else policy["nb_mob_for_reward"]
    )
    if (
        len(objectives) != 1
        or objectives[0]["family"] != expected_family
        or profile["minimum_contribution"] != threshold
        or (
            profile["mode"] != "collaborative"
            and objectives[0]["required_quantity"] != threshold
        )
    ):
        raise ValueError("Environmental random contribution/goal differs from original")
    if (
        objectives[0]["target_reference"] not in (None, policy["group_reference"])
        and expected_family == "group_defeat"
    ):
        raise ValueError(
            "Environmental group reference differs from its original source"
        )
    records = db.execute(
        "SELECT n.* FROM environmental_random_roster_species s JOIN environmental_random_native_species n "
        "USING(monster_reference) WHERE s.source_key=%s AND s.scenario_id=%s AND s.policy_version=%s ORDER BY monster_reference",
        (policy["source_key"], policy["scenario_id"], policy["policy_version"]),
    ).fetchall()
    if not records:
        raise ValueError("Environmental exact species catalog changed")
    from wakfu_server.native_catalog_compatibility import require_source_revision

    for revision in {row["catalog_revision"] for row in records}:
        require_source_revision(revision, ("monsters.json",))
    species = {r["monster_reference"]: r["native_min_level"] for r in records}
    if (
        expected_family in ("monster_defeat", "monster_destroy")
        and objectives[0]["target_reference"] is not None
        and set(species) != {objectives[0]["target_reference"]}
    ):
        raise ValueError(
            "Environmental aggregate kill objective excludes original species"
        )
    if expected_family == "monster_destroy":
        from .environmental_monster_actions import native_destroy_action

        sources = db.execute(
            "SELECT s.* FROM environmental_profile_destroy_policy p "
            "JOIN environmental_destroy_sources s "
            "USING(source_key,scenario_id,policy_version,monster_reference,action_id) "
            "WHERE p.profile_key=%s AND p.version=%s",
            (profile["profile_key"], profile["version"]),
        ).fetchall()
        for revision in {row["catalog_revision"] for row in sources}:
            require_source_revision(revision, ("monster-encyclopedia.json",))
        if (
            not sources
            or {r["monster_reference"] for r in sources} != set(species)
            or any(
                r["scenario_id"] != policy["scenario_id"]
                or r["source_key"] != policy["source_key"]
                or r["template_reference"] != policy["group_reference"]
                or r["descriptor_sha256"] != _digest(r["action_descriptor"])
                or native_destroy_action(r["monster_reference"], r["action_id"])[
                    "native"
                ]
                != r["action_descriptor"]
                for r in sources
            )
            or objectives[0]["action_id"] is not None
            and {r["action_id"] for r in sources} != {objectives[0]["action_id"]}
        ):
            raise ValueError(
                "Environmental destruction population lacks exact native action sources"
            )
    seed, slots = _draw(db, event, policy, species)
    # Include all physical groups and pending births, including non-ecological
    # actors; ordinary ecological budgets must not erase collision or capacity.
    groups = physical_groups(db, event["map_id"], event["world_instance_id"])
    pending = pending_growth_groups(
        db,
        event["map_id"],
        event["world_instance_id"],
        existing_group_ids={g["group_id"] for g in groups},
    )
    if (
        len(groups) + len(pending) + policy["group_count"] > policy["max_zone_groups"]
        or sum(len(g["members"]) for g in [*groups, *pending]) + len(slots)
        > policy["max_zone_members"]
    ):
        return {}
    positions, adjacency = _geometry(
        native_catalog.release(), event["map_id"], event["region_id"]
    )
    blocked = (
        set(taken)
        | _scene_cells(db, event["map_id"], event["world_instance_id"])
        | {
            (p[0], p[1])
            for p in physical_cells(db, event["map_id"], event["world_instance_id"])
        }
    )
    actor_profiles = native_actor_catalog()["npc_profiles"]
    for group in pending:
        for member in group["members"]:
            blocked.update(
                footprint(
                    (member["x"], member["y"]),
                    actor_profiles[str(member["ref"])]["physical_radius"],
                )
            )
    by_group = defaultdict(list)
    for row in slots:
        by_group[row["group_ordinal"]].append(row)
    result = {}
    connected = [point for point in positions if adjacency[point]]
    step = max(1, (len(connected) + 255) // 256)
    for ordinal, members in sorted(by_group.items()):
        anchors = sorted(connected[::step], key=lambda p: _digest([seed, ordinal, p]))
        chosen = None
        for anchor in anchors:
            queue = deque([anchor])
            seen = {anchor}
            reserved = set()
            assigned = []
            while queue and len(assigned) < len(members) and len(seen) <= 64:
                point = queue.popleft()
                if (point[0], point[1]) in blocked:
                    continue
                row = members[len(assigned)]
                occupied = set(
                    footprint(
                        point[:2],
                        actor_profiles[str(row["monster_reference"])][
                            "physical_radius"
                        ],
                    )
                )
                if not occupied.intersection(blocked | reserved) and all(
                    (x, y, point[2]) in adjacency for x, y in occupied
                ):
                    assigned.append(
                        dict(
                            row,
                            x=point[0],
                            y=point[1],
                            z=point[2],
                            group_reference=policy["group_reference"],
                        )
                    )
                    reserved.update(occupied)
                for neighbor in adjacency[point]:
                    if neighbor not in seen:
                        seen.add(neighbor)
                        queue.append(neighbor)
            if len(assigned) == len(members):
                chosen = (assigned, reserved)
                break
        if chosen is None:
            return {}
        result[ordinal] = chosen[0]
        blocked.update(chosen[1])
    return result
