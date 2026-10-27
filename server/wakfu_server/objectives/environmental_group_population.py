"""Event-owned durable groups from explicit versioned Wakemu roster policies.

Positive native breed parameters constrain membership, not original type74
quantities. The caller owns transaction/commit and native outbox publication.
"""
from collections import Counter, defaultdict
from hashlib import sha256
import json

from . import environmental_presence as presence
from . import environmental_runtime as rules
from . import environmental_storage as storage


def _roster_digest(members):
    # Native wandering can move a durable group without changing its identity.
    rows = [
        {key: value for key, value in row.items() if key not in ("x", "y", "z")}
        for row in members
    ]
    return sha256(
        json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _plan(db, event, profile, policy):
    from wakfu_server.monsters import owned_instance
    from wakfu_server.planting_cells import surface

    if (
        policy["policy_contract"] != "wakemu.explicit-native-breed-roster.v1"
        or profile["native_scenario_id"] != policy["native_scenario_id"]
        or profile["family"] not in ("group_defeat", "monster_defeat")
    ):
        raise ValueError(
            "Environmental population differs from declared scenario/family"
        )
    native = db.execute(
        "SELECT native_type FROM environmental_native_scenarios WHERE source_key=%s AND scenario_id=%s",
        (policy["source_key"], policy["native_scenario_id"]),
    ).fetchone()
    if native is None or native["native_type"] not in (6, 7, 8):
        raise ValueError("Environmental source is not a fight/herd/invasion scenario")
    parameters = db.execute(
        "SELECT normalized_key,native_value FROM environmental_native_configuration "
        "WHERE source_key=%s AND scenario_id=%s",
        (policy["source_key"], policy["native_scenario_id"]),
    ).fetchall()
    allowed = set()
    for row in parameters:
        if row["normalized_key"] in (
            "specialbreedid",
            *(f"breedid{index}" for index in range(1, 7)),
        ):
            try:
                value = int(row["native_value"])
            except ValueError as error:
                raise ValueError(
                    "Malformed original explicit environmental breed"
                ) from error
            if value > 0:
                allowed.add(value)
    declared = db.execute(
        "SELECT group_reference,monster_reference,quantity FROM environmental_profile_group_composition "
        "WHERE profile_key=%s AND version=%s",
        (event["profile_key"], event["version"]),
    ).fetchall()
    compositions = defaultdict(dict)
    for row in declared:
        compositions[row["group_reference"]][row["monster_reference"]] = row["quantity"]
    rows = db.execute(
        "SELECT * FROM environmental_profile_group_cells WHERE profile_key=%s AND version=%s "
        "ORDER BY group_ordinal,member_ordinal",
        (event["profile_key"], event["version"]),
    ).fetchall()
    if not rows or len(rows) > 4096:
        raise ValueError("Missing or excessive explicit environmental group placement")
    if len({(row["x"], row["y"]) for row in rows}) != len(rows):
        raise ValueError("Environmental group placements share a native XY cell")
    plans = defaultdict(list)
    for row in rows:
        if row["monster_reference"] not in allowed:
            raise ValueError(
                "Environmental roster lacks a positive original breed parameter"
            )
        if not profile["level_min"] <= row["native_level"] <= profile["level_max"]:
            raise ValueError("Environmental actor level differs from its profile")
        if (
            surface(event["map_id"], row["x"], row["y"], row["z"])["region_id"]
            != event["region_id"]
        ):
            raise ValueError(
                "Environmental group placement leaves its exact native region"
            )
        owned_instance(
            row["monster_reference"],
            row["native_level"],
            -1,
            map_id=event["map_id"],
            instance_id=event["world_instance_id"],
            x=row["x"],
            y=row["y"],
            z=row["z"],
        )
        plans[row["group_ordinal"]].append(row)
    if sorted(plans) != list(range(len(plans))):
        raise ValueError("Environmental group ordinals are not contiguous")
    for members in plans.values():
        refs = {row["group_reference"] for row in members}
        if len(refs) != 1 or [row["member_ordinal"] for row in members] != list(
            range(len(members))
        ):
            raise ValueError("Environmental group placement has ambiguous composition")
        if (
            Counter(row["monster_reference"] for row in members)
            != compositions[next(iter(refs))]
        ):
            raise ValueError(
                "Environmental group placement differs from declared quantities"
            )
    return plans


def populate(db, event, groups, *, now_ms):
    """Create all declared groups and ownership atomically, once per event.

    Return group keys for post-commit publication. A persisted spawn outbox also
    records retries; this function does not send sockets or alter live registries.
    """
    occupied = presence.capture(event["map_id"], event["world_instance_id"])
    if occupied is None or event.get("state") != "active":
        return ()
    storage._transaction(db)
    rules.integer(now_ms, "group population clock")
    storage._scope_lock(db, event["map_id"], event["world_instance_id"])
    if not presence.current(occupied, event["map_id"], event["world_instance_id"]):
        return ()
    fresh = db.execute(
        "SELECT * FROM environmental_event_instances WHERE instance_id=%s FOR UPDATE",
        (event["instance_id"],),
    ).fetchone()
    if fresh is None or (fresh["map_id"], fresh["world_instance_id"]) != (
        event["map_id"],
        event["world_instance_id"],
    ):
        raise ValueError("Environmental group event scope changed")
    event = fresh
    if (
        event["state"] != "active"
        or not event["started_at_ms"] <= now_ms < event["deadline_ms"]
    ):
        return ()
    profile = storage._event_profile(db, event)
    if not profile["enabled"] or profile["family"] not in (
        "group_defeat",
        "monster_defeat",
        "monster_destroy",
    ):
        return ()
    policy = db.execute(
        "SELECT * FROM environmental_profile_group_population WHERE profile_key=%s AND version=%s",
        (event["profile_key"], event["version"]),
    ).fetchone()
    random_policy = None
    if profile["family"] == "monster_destroy" and policy is not None:
        raise ValueError(
            "Native destruction requires its qualified random source policy"
        )
    if policy is None:
        from .environmental_random_rosters import binding

        random_policy = binding(db, event)
        if random_policy is None:
            return ()
    from wakfu_server import native_catalog

    from wakfu_server.native_catalog_compatibility import require_source_revision

    require_source_revision(
        profile["catalog_revision"],
        (
            "monsters.json",
            "monster-encyclopedia.json",
            "territory-map-cells.json",
            "territory-protector-bonuses.json",
        ),
    )
    # An event never refills defeated/depleted originals.
    if (
        db.execute(
            "SELECT 1 FROM environmental_owned_groups WHERE instance_id=%s LIMIT 1",
            (event["instance_id"],),
        ).fetchone()
        is not None
    ):
        return ()
    plans = _plan(db, event, profile, policy) if random_policy is None else None
    if not db.execute(
        "SELECT pg_try_advisory_xact_lock(hashtextextended(%s,0)) AS held",
        (f"monster-population:{event['map_id']}:{event['world_instance_id']}",),
    ).fetchone()["held"]:
        return ()
    taken = set()
    for row in db.execute(
        "SELECT members FROM combat_groups WHERE map_id=%s AND instance_id=%s AND status!='defeated'",
        (event["map_id"], event["world_instance_id"]),
    ).fetchall():
        taken.update((member["x"], member["y"]) for member in row["members"])
    taken.update(
        (row["x"], row["y"])
        for row in db.execute(
            "SELECT x,y FROM planted_resources WHERE map_id=%s AND instance_id=%s",
            (event["map_id"], event["world_instance_id"]),
        ).fetchall()
    )
    for table in ("mining_vein_slots", "fishing_spot_slots"):
        taken.update(
            (row["x"], row["y"])
            for row in db.execute(
                f"SELECT x,y FROM {table} WHERE map_id=%s AND instance_id=%s AND enabled",
                (event["map_id"], event["world_instance_id"]),
            ).fetchall()
        )
    world = occupied[0]
    with world.lock:
        taken.update(
            (row["x"], row["y"])
            for _, _, row in world.players.values()
            if world.location(row) == (event["map_id"], event["world_instance_id"])
        )
    if random_policy is not None:
        from .environmental_random_rosters import plan

        plans = plan(db, event, profile, random_policy, taken=taken)
        if not plans:
            return ()
    for members in plans.values():
        for row in members:
            key = f"planting-cell:{event['map_id']}:{event['world_instance_id']}:{row['x']}:{row['y']}"
            if (row["x"], row["y"]) in taken or not db.execute(
                "SELECT pg_try_advisory_xact_lock(hashtextextended(%s,0)) AS held",
                (key,),
            ).fetchone()["held"]:
                return ()  # No partial spawn or overwrite of player activity.
            if (
                db.execute(
                    "SELECT 1 FROM planted_resources WHERE map_id=%s AND instance_id=%s AND x=%s AND y=%s",
                    (event["map_id"], event["world_instance_id"], row["x"], row["y"]),
                ).fetchone()
                is not None
            ):
                return ()
    if not presence.current(occupied, event["map_id"], event["world_instance_id"]):
        return ()
    from wakfu_server.monsters import owned_instance
    from wakfu_server.npc_actor_identity import allocate_block

    keys = []
    for ordinal, plan in plans.items():
        identities = [allocate_block(db, 1) for _ in plan]
        members = [
            owned_instance(
                row["monster_reference"],
                row["native_level"],
                -identity,
                map_id=event["map_id"],
                instance_id=event["world_instance_id"],
                x=row["x"],
                y=row["y"],
                z=row["z"],
            )
            for row, identity in zip(plan, identities)
        ]
        if profile["family"] == "monster_destroy":
            for member in members:
                member["environmental_world_action_only"] = True
        key = groups.register_transaction(
            db, event["map_id"], event["world_instance_id"], identities[0], members
        )
        source = f"event-group:{event['instance_id']}:{ordinal}"
        reference = plan[0]["group_reference"]
        db.execute(
            "INSERT INTO environmental_owned_groups VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,NULL)",
            (
                event["instance_id"],
                ordinal,
                key[2],
                *key[:2],
                reference,
                source,
                _roster_digest(members),
                now_ms,
            ),
        )
        group = db.execute(
            "SELECT revision FROM combat_groups WHERE map_id=%s AND instance_id=%s AND group_id=%s",
            key,
        ).fetchone()
        memberships = [
            dict(
                entity_kind="group",
                entity_id=key[2],
                reference=reference,
                source_key=source,
                spawn_owned=True,
            )
        ]
        for member in members:
            db.execute(
                "INSERT INTO environmental_owned_group_members VALUES(%s,%s,%s,%s,%s)",
                (
                    event["instance_id"],
                    ordinal,
                    member["id"],
                    member["ref"],
                    member["level"],
                ),
            )
            if profile["family"] == "monster_defeat" or random_policy is not None:
                memberships.append(
                    dict(
                        entity_kind="monster",
                        entity_id=member["id"],
                        reference=member["ref"],
                        source_key=source + ":" + str(member["id"]),
                        spawn_owned=True,
                    )
                )
        if storage.register_memberships(db, event["instance_id"], memberships) is False:
            raise ValueError("Environmental group lost occupied admission")
        db.execute(
            "INSERT INTO environmental_event_groups(instance_id,group_id,admitted_revision) VALUES(%s,%s,%s)",
            (event["instance_id"], key[2], group["revision"]),
        )
        for member in members:
            db.execute(
                "INSERT INTO environmental_event_group_members VALUES(%s,%s,%s,%s)",
                (event["instance_id"], key[2], member["id"], member["ref"]),
            )
        db.execute(
            "INSERT INTO environmental_group_publications VALUES(%s,%s,'spawn',%s,NULL,NULL)",
            (event["instance_id"], ordinal, now_ms),
        )
        keys.append(key)
    if not presence.current(occupied, event["map_id"], event["world_instance_id"]):
        raise ValueError(
            "Environmental group lost occupied admission during population"
        )
    return tuple(keys)


def _remaining_destroy_members(db, owned, group):
    """Validate a consumed birth roster; leave legacy groups on their old path.

    A retired group has no physical row. Its despawn projection is derived from
    the immutable birth snapshot and removal ledger, then checked by the same
    native-removal verifier used before retirement.
    """
    tables = db.execute(
        "SELECT to_regclass('environmental_monster_destructions') AS ledger, "
        "to_regclass('environmental_destroy_rosters') AS births"
    ).fetchone()
    if tables["ledger"] is None or tables["births"] is None:
        return None
    removed = db.execute(
        "SELECT monster_id FROM environmental_monster_destructions "
        "WHERE instance_id=%s AND group_ordinal=%s",
        (owned["instance_id"], owned["group_ordinal"]),
    ).fetchall()
    if not removed:
        return None
    from .environmental_monster_destroy import (
        remaining_birth_members,
        verify_group_roster,
    )

    if group is None:
        remaining = remaining_birth_members(db, owned)
        if remaining is None:
            raise ValueError("Environmental removal ledger lacks its birth snapshot")
        return remaining
    return verify_group_roster(db, owned, group)


def cleanup(db, *, map_id, instance_id, now_ms, limit=64):
    """Retire only authenticated owned groups; never delete a live fight lease."""
    occupied = presence.capture(map_id, instance_id)
    if occupied is None:
        return ()
    storage._transaction(db)
    rules.integer(now_ms, "group retirement clock")
    rules.integer(limit, "group cleanup limit", minimum=1)
    if limit > 256:
        raise ValueError("Environmental group cleanup exceeds its bound")
    storage._scope_lock(db, map_id, instance_id)
    if not presence.current(occupied, map_id, instance_id):
        return ()
    if not db.execute(
        "SELECT pg_try_advisory_xact_lock(hashtextextended(%s,0)) AS held",
        (f"monster-population:{map_id}:{instance_id}",),
    ).fetchone()["held"]:
        return ()
    rows = db.execute(
        "SELECT o.* FROM environmental_owned_groups o JOIN environmental_event_instances e USING(instance_id) "
        "WHERE o.map_id=%s AND o.world_instance_id=%s AND e.state IN ('completed','expired','cancelled') "
        "AND o.retired_at_ms IS NULL ORDER BY o.instance_id,o.group_ordinal LIMIT %s FOR UPDATE OF o SKIP LOCKED",
        (map_id, instance_id, limit),
    ).fetchall()
    retired = []
    for owned in rows:
        key = (map_id, instance_id, owned["group_id"])
        group = db.execute(
            "SELECT * FROM combat_groups WHERE map_id=%s AND instance_id=%s AND group_id=%s FOR UPDATE",
            key,
        ).fetchone()
        if group is None:
            raise ValueError(
                "Environmental owned group disappeared without retirement authority"
            )
        if group["status"] == "fighting":
            continue
        remaining = _remaining_destroy_members(db, owned, group)
        if (
            remaining is None
            and _roster_digest(group["members"]) != owned["roster_sha256"]
        ):
            raise ValueError("Environmental owned group provenance changed")
        membership = db.execute(
            "SELECT * FROM environmental_event_memberships WHERE instance_id=%s AND entity_kind='group' AND entity_id=%s",
            (owned["instance_id"], key[2]),
        ).fetchone()
        if (
            membership is None
            or not membership["spawn_owned"]
            or membership["source_key"] != owned["source_key"]
            or membership["reference"] != owned["group_reference"]
        ):
            raise ValueError("Environmental group cleanup lacks exact ownership")
        db.execute(
            "DELETE FROM combat_groups WHERE map_id=%s AND instance_id=%s AND group_id=%s",
            key,
        )
        db.execute(
            "UPDATE environmental_owned_groups SET retired_at_ms=%s WHERE instance_id=%s AND group_ordinal=%s",
            (now_ms, owned["instance_id"], owned["group_ordinal"]),
        )
        db.execute(
            "UPDATE environmental_group_publications SET superseded_at_ms=%s WHERE instance_id=%s AND group_ordinal=%s "
            "AND kind='spawn' AND published_at_ms IS NULL",
            (now_ms, owned["instance_id"], owned["group_ordinal"]),
        )
        db.execute(
            "INSERT INTO environmental_group_publications VALUES(%s,%s,'despawn',%s,NULL,NULL) ON CONFLICT DO NOTHING",
            (owned["instance_id"], owned["group_ordinal"], now_ms),
        )
        db.execute(
            "UPDATE environmental_cleanup_outbox SET completed_at_ms=%s WHERE instance_id=%s AND action='despawn_owned' "
            "AND (entity_kind='group' AND entity_id=%s OR entity_kind='monster' AND entity_id IN "
            "(SELECT monster_id FROM environmental_owned_group_members WHERE instance_id=%s AND group_ordinal=%s))",
            (
                now_ms,
                owned["instance_id"],
                key[2],
                owned["instance_id"],
                owned["group_ordinal"],
            ),
        )
        retired.append(key)
    return tuple(retired)
