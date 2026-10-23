"""Occupied native archmonster births, independent of environmental quests.

Single-member native groups retain ordinary combat, stats and loot. Announcements
have a ten-second occurrence window; monsters have no announcement-based TTL.
"""
from collections import Counter
from hashlib import sha256
import json
import re

from . import environmental_presence as presence
from . import environmental_storage as storage
from .environmental_runtime import integer


CONTRACT = "wakemu.native-count-archmonster-world-birth.v1"
REGION_PAUSE_MS = 70000  # Declared 10-second announcement plus 60-second separation.


def _digest(value):
    return sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _policy(db):
    row = db.execute(
        "SELECT p.* FROM archmonster_spawn_active a "
        "JOIN archmonster_spawn_policy_versions p USING(policy_version) "
        "WHERE a.singleton AND a.enabled"
    ).fetchone()
    if row is not None and (
        row["policy_contract"] != CONTRACT
        or row["member_count"] != 1
        or type(row["cooldown_ms"]) is not int
        or row["cooldown_ms"] <= 0
    ):
        raise ValueError("Invalid immutable archmonster birth policy")
    return row


def region_pause(db, *, location, now_ms):
    """Delay only a new environmental selection after an enabled actual birth."""
    if location.get("region_id") is None:
        return False
    if presence.capture(location["map_id"], location["instance_id"]) is None:
        return False
    storage._transaction(db)
    integer(now_ms, "archmonster pause clock")
    if _policy(db) is None:
        return False
    return (
        db.execute(
            "SELECT 1 FROM archmonster_spawn_births WHERE map_id=%s "
            "AND world_instance_id=%s AND region_id=%s AND spawned_at_ms<=%s "
            "AND spawned_at_ms+%s>%s LIMIT 1",
            (
                location["map_id"],
                location["instance_id"],
                location["region_id"],
                now_ms,
                REGION_PAUSE_MS,
                now_ms,
            ),
        ).fetchone()
        is not None
    )


def _counts(db, map_id, instance_id, region_id):
    from wakfu_server.ecology_context import population_region

    counts = Counter()
    for group in db.execute(
        "SELECT members FROM combat_groups WHERE map_id=%s "
        "AND instance_id=%s AND status!='defeated'",
        (map_id, instance_id),
    ):
        for member in group["members"]:
            if type(member.get("hp")) is not int or type(member.get("ref")) is not int:
                raise ValueError("Missing actual archmonster population HP/breed")
            if member["hp"] <= 0:
                continue
            try:
                region = population_region(
                    map_id, member["x"], member["y"], member["z"]
                )["region_id"]
            except ValueError:
                return None  # An unresolved living position cannot prove a low count.
            if region == region_id:
                counts[member["ref"]] += 1
    return counts


def _eligible(db, source, counts):
    if source["blocked_by_membership"]:
        return False
    members = db.execute(
        "SELECT * FROM archmonster_spawn_memberships WHERE source_key=%s "
        "AND scenario_id=%s ORDER BY group_id",
        (source["source_key"], source["scenario_id"]),
    ).fetchall()
    if not members:
        raise ValueError("Archmonster lacks original membership predicates")
    eligible = False
    for member in members:
        if member["literal_false"]:
            continue
        predicates = db.execute(
            "SELECT * FROM archmonster_spawn_predicates WHERE source_key=%s "
            "AND scenario_id=%s AND group_id=%s ORDER BY ordinal",
            (source["source_key"], source["scenario_id"], member["group_id"]),
        ).fetchall()
        if (
            len(predicates) != 2
            or {p["function_name"] for p in predicates}
            != {"GetMonsterCountInZone", "GetNbMonstersInZone"}
            or any(
                p["reference"] != source["monster_reference"]
                or p["comparison"] != "<"
                or p["threshold"] != 4
                for p in predicates
            )
        ):
            raise ValueError("Unsupported original archmonster count predicate")
        expected = "and".join(
            f"{p['function_name']}({p['reference']})<4" for p in predicates
        )
        if re.sub(r"\s+", "", member["original_criterion"]) != expected:
            raise ValueError(
                "Archmonster normalized predicates differ from original text"
            )
        eligible |= all(counts[p["reference"]] < p["threshold"] for p in predicates)
    return eligible


def _birth(db, store, groups, location, now_ms, occupied):
    from wakfu_server import native_catalog
    from wakfu_server.monsters import owned_instance, reference
    from wakfu_server.npc_actor_identity import allocate_block
    from .environmental_archmonster_geometry import plan_geometry

    policy = _policy(db)
    if policy is None or region_pause(db, location=location, now_ms=now_ms):
        return None
    scope = (location["map_id"], location["instance_id"], location["region_id"])
    # Native archmonster notifications do not replace the regional quest.
    # Continuous quest windows must not prevent independent world births.
    counts = _counts(db, *scope)
    if counts is None:
        return None
    sources = db.execute(
        "SELECT s.*,COALESCE(c.cooldown_ms,%s) AS effective_cooldown "
        "FROM archmonster_spawn_sources s JOIN archmonster_spawn_scopes b USING(source_key,scenario_id) "
        "LEFT JOIN archmonster_spawn_cadences c ON c.source_key=s.source_key "
        "AND c.scenario_id=s.scenario_id AND c.policy_version=%s "
        "WHERE b.map_id=%s AND b.region_id=%s ORDER BY s.scenario_id",
        (policy["cooldown_ms"], policy["policy_version"], scope[0], scope[2]),
    ).fetchall()
    for source in sources:
        if not _eligible(db, source, counts):
            continue
        if (
            source["requested_group_count"] != 1
            or source["participation_criterion"] != "False"
            or source["announcement_duration_ms"] != 10000
            or source["catalog_revision"] != native_catalog.release()
        ):
            raise ValueError("Archmonster source differs from original birth contract")
        last = db.execute(
            "SELECT cooldown_until_ms FROM archmonster_spawn_births "
            "WHERE source_key=%s AND scenario_id=%s AND map_id=%s AND region_id=%s "
            "AND world_instance_id=%s ORDER BY spawned_at_ms DESC LIMIT 1",
            (source["source_key"], source["scenario_id"], scope[0], scope[2], scope[1]),
        ).fetchone()
        if last is not None and now_ms < last["cooldown_until_ms"]:
            continue
        native = db.execute(
            "SELECT native_type,duration_raw FROM environmental_native_scenarios "
            "WHERE source_key=%s AND scenario_id=%s",
            (source["source_key"], source["scenario_id"]),
        ).fetchone()
        with native_catalog._database().connection() as catalog_db:
            document = catalog_db.execute(
                "SELECT sha256 FROM native_catalog_documents WHERE revision=%s AND path='monsters.json'",
                (source["catalog_revision"],),
            ).fetchone()
        breed = reference(source["monster_reference"])
        if (
            native is None
            or native["native_type"] != 4
            or native["duration_raw"] != 10
            or document is None
            or document["sha256"] != source["monsters_sha256"]
            or (breed["min_level"], breed["max_level"])
            != (source["native_min_level"], source["native_max_level"])
        ):
            raise ValueError("Archmonster native type, level or catalog changed")
        point = plan_geometry(
            db,
            scope[0],
            scope[1],
            scope[2],
            source["monster_reference"],
            source["native_min_level"],
            taken=(),
        )
        if point is None:
            continue
        from wakfu_server.combat_actor_snapshot import native_actor_catalog
        from wakfu_server.combat_obstacle_condition import footprint

        radius = native_actor_catalog()["npc_profiles"][
            str(source["monster_reference"])
        ]["physical_radius"]
        for x, y in sorted(footprint(point[:2], radius)):
            if not db.execute(
                "SELECT pg_try_advisory_xact_lock(hashtextextended(%s,0)) AS held",
                (f"planting-cell:{scope[0]}:{scope[1]}:{x}:{y}",),
            ).fetchone()["held"]:
                return None
            if (
                db.execute(
                    "SELECT 1 FROM planted_resources WHERE map_id=%s AND instance_id=%s "
                    "AND x=%s AND y=%s",
                    (scope[0], scope[1], x, y),
                ).fetchone()
                is not None
            ):
                return None
        if not presence.current(occupied, *scope[:2]):
            return None
        identity = allocate_block(db, 1)
        monster = owned_instance(
            source["monster_reference"],
            source["native_min_level"],
            -identity,
            map_id=scope[0],
            instance_id=scope[1],
            x=point[0],
            y=point[1],
            z=point[2],
        )
        groups.register_transaction(db, scope[0], scope[1], identity, [monster])
        cooldown = source["effective_cooldown"]
        if type(cooldown) is not int or cooldown <= 0:
            raise ValueError("Missing declared archmonster cooldown")
        spawn_id = _digest(
            [
                policy["policy_version"],
                source["source_key"],
                source["scenario_id"],
                *scope,
                now_ms,
            ]
        )
        db.execute(
            "INSERT INTO archmonster_spawn_births "
            "(spawn_id,source_key,scenario_id,map_id,region_id,world_instance_id,epoch_ms,policy_version,"
            "group_id,monster_id,monster_reference,native_level,spawned_at_ms,cooldown_ms,cooldown_until_ms) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                spawn_id,
                source["source_key"],
                source["scenario_id"],
                scope[0],
                scope[2],
                scope[1],
                now_ms,
                policy["policy_version"],
                identity,
                -identity,
                source["monster_reference"],
                source["native_min_level"],
                now_ms,
                cooldown,
                now_ms + cooldown,
            ),
        )
        db.execute(
            "INSERT INTO archmonster_spawn_publications(spawn_id,created_at_ms) VALUES(%s,%s)",
            (spawn_id, now_ms),
        )
        if not presence.current(occupied, *scope[:2]):
            raise ValueError("Archmonster birth lost its occupied scope")
        return spawn_id  # At most one real birth per region poll.
    return None


def _current(row):
    members = row["members"]
    if (
        len(members) != 1
        or members[0]["id"] != row["monster_id"]
        or members[0]["ref"] != row["monster_reference"]
        or members[0]["level"] != row["native_level"]
        or members[0]["hp"] <= 0
        or members[0]["map_id"] != row["map_id"]
        or members[0]["instance_id"] != row["world_instance_id"]
    ):
        raise ValueError("Archmonster current group differs from its immutable birth")
    return _digest(members)


def _publish(store, world, location, now_ms, occupied):
    from wakfu_server.combat_monster_world import spawn_group
    from .environmental_world import notification_packet

    with store.connection() as db:
        rows = db.execute(
            "SELECT b.*,g.members,g.revision FROM archmonster_spawn_publications p "
            "JOIN archmonster_spawn_births b USING(spawn_id) JOIN combat_groups g "
            "ON g.map_id=b.map_id AND g.instance_id=b.world_instance_id AND g.group_id=b.group_id "
            "WHERE b.map_id=%s AND b.world_instance_id=%s AND b.region_id=%s AND g.status='available' "
            "AND p.published_at_ms IS NULL ORDER BY b.spawned_at_ms,b.spawn_id LIMIT 64",
            (location["map_id"], location["instance_id"], location["region_id"]),
        ).fetchall()
    for row in rows:
        if not presence.current(occupied, location["map_id"], location["instance_id"]):
            break
        digest = _current(row)
        publication_ms = max(now_ms, int(store.now().timestamp() * 1000))
        packets = [(12608, spawn_group(row["members"], group_id=row["group_id"]))]
        if row["spawned_at_ms"] <= publication_ms < row["spawned_at_ms"] + 10000:
            packets.append(notification_packet(row["scenario_id"]))
        if not world.emit_location_batch(
            row["map_id"], row["world_instance_id"], tuple(packets), require_all=True
        ):
            continue
        with store.connection() as db:
            current = db.execute(
                "SELECT b.*,g.members,g.revision FROM archmonster_spawn_births b "
                "JOIN combat_groups g ON g.map_id=b.map_id AND g.instance_id=b.world_instance_id "
                "AND g.group_id=b.group_id WHERE b.spawn_id=%s AND g.status='available' FOR SHARE OF g",
                (row["spawn_id"],),
            ).fetchone()
            if (
                current is not None
                and current["revision"] == row["revision"]
                and _current(current) == digest
                and presence.current(occupied, row["map_id"], row["world_instance_id"])
            ):
                db.execute(
                    "UPDATE archmonster_spawn_publications SET published_at_ms=%s "
                    "WHERE spawn_id=%s AND published_at_ms IS NULL",
                    (publication_ms, row["spawn_id"]),
                )


def poll(store, world, groups, *, location, now_ms):
    """Commit one eligible birth, then publish/retry current ordinary groups."""
    map_id, instance_id, region_id = (
        location.get(key) for key in ("map_id", "instance_id", "region_id")
    )
    if region_id is None:
        return ()
    occupied = presence.capture(map_id, instance_id, world=world)
    if occupied is None:
        return ()  # No SQL, catalog or geometry work for a vacant scope.
    for value, label, minimum in (
        (map_id, "map", 1),
        (instance_id, "instance", 0),
        (region_id, "region", 1),
        (now_ms, "clock", 0),
    ):
        integer(value, "archmonster " + label, minimum=minimum)
    if groups.store is not store:
        raise ValueError("Archmonster registry belongs to another Store")
    with groups.lock:
        with store.connection() as db:
            storage._scope_lock(db, map_id, instance_id)
            db.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                (f"monster-population:{map_id}:{instance_id}",),
            )
            born = (
                _birth(db, store, groups, location, now_ms, occupied)
                if presence.current(occupied, map_id, instance_id)
                else None
            )
        _publish(store, world, location, now_ms, occupied)
    return () if born is None else (born,)
