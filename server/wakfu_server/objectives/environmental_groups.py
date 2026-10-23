"""Exact declared environmental groups and authenticated original-group wins.

No breed-only kill is promoted into a group victory. Group composition is
sealed SQL authority; native group templates are not inferred from names.
"""
from collections import Counter
from . import environmental_presence as presence
from . import environmental_runtime as rules


def bind_available(db, event):
    """An explicit profile policy may bind exact available declared populations."""
    from . import environmental_storage as storage

    occupied = presence.capture(event["map_id"], event["world_instance_id"])
    if occupied is None or event.get("state") != "active":
        return ()
    storage._transaction(db)
    storage._scope_lock(db, event["map_id"], event["world_instance_id"])
    if not presence.current(occupied, event["map_id"], event["world_instance_id"]):
        return ()
    enabled = db.execute(
        "SELECT 1 FROM environmental_profile_bindings WHERE profile_key=%s AND version=%s "
        "AND producer='existing_declared_groups'",
        (event["profile_key"], event["version"]),
    ).fetchone()
    if enabled is None:
        return ()
    rows = db.execute(
        "SELECT group_reference,monster_reference,quantity FROM environmental_profile_group_composition "
        "WHERE profile_key=%s AND version=%s",
        (event["profile_key"], event["version"]),
    ).fetchall()
    templates = {}
    for row in rows:
        templates.setdefault(row["group_reference"], {})[
            row["monster_reference"]
        ] = row["quantity"]
    groups = db.execute(
        "SELECT g.group_id,g.members,g.revision FROM combat_groups g "
        "WHERE g.map_id=%s AND g.instance_id=%s AND g.status='available' AND NOT EXISTS "
        "(SELECT 1 FROM environmental_event_groups e WHERE e.instance_id=%s AND e.group_id=g.group_id) "
        "ORDER BY g.group_id",
        (event["map_id"], event["world_instance_id"], event["instance_id"]),
    ).fetchall()
    bound = []
    from .environmental_gameplay import _native_region

    for group in groups:
        refs = Counter(row["ref"] for row in group["members"])
        matching = [
            reference
            for reference, composition in templates.items()
            if refs == composition
        ]
        # Never choose between two template identities with the same breeds.
        if len(matching) != 1 or any(
            _native_region(event["map_id"], row) != event["region_id"]
            for row in group["members"]
        ):
            continue
        if bind(
            db,
            event["instance_id"],
            group_id=group["group_id"],
            group_reference=matching[0],
            source_key=f"existing-group:{group['group_id']}:{group['revision']}",
        ):
            bound.append(group["group_id"])
    return tuple(bound)


def bind(db, instance_id, *, group_id, group_reference, source_key):
    """Bind an available durable group, retaining its exact original population."""
    from . import environmental_storage as storage
    from .environmental_gameplay import _native_region

    storage._transaction(db)
    rules.integer(group_id, "world group", minimum=1)
    rules.integer(group_reference, "group reference", minimum=1)
    if (
        group_reference >= 2**31
        or type(source_key) is not str
        or not 1 <= len(source_key) <= 160
    ):
        raise ValueError("Invalid environmental group source identity")
    scope = db.execute(
        "SELECT map_id,world_instance_id FROM environmental_event_instances WHERE instance_id=%s",
        (instance_id,),
    ).fetchone()
    if scope is None:
        raise ValueError("Missing environmental group instance")
    occupied = presence.capture(scope["map_id"], scope["world_instance_id"])
    if occupied is None:
        return False
    storage._scope_lock(db, scope["map_id"], scope["world_instance_id"])
    if not presence.current(occupied, scope["map_id"], scope["world_instance_id"]):
        return False
    event = db.execute(
        "SELECT * FROM environmental_event_instances WHERE instance_id=%s FOR UPDATE",
        (instance_id,),
    ).fetchone()
    if event["state"] not in ("proposed", "active"):
        raise ValueError("Environmental group requires an admitted event")
    profile = storage._event_profile(db, event)
    if profile["family"] not in ("group_defeat", "monster_defeat"):
        raise ValueError("Environmental group producer differs from the profile family")
    declared = db.execute(
        "SELECT monster_reference,quantity FROM environmental_profile_group_composition "
        "WHERE profile_key=%s AND version=%s AND group_reference=%s",
        (event["profile_key"], event["version"], group_reference),
    ).fetchall()
    group = db.execute(
        "SELECT members,status,revision FROM combat_groups WHERE map_id=%s AND instance_id=%s AND group_id=%s",
        (event["map_id"], event["world_instance_id"], group_id),
    ).fetchone()
    if group is None or group["status"] != "available" or not declared:
        raise ValueError("Missing available world group or declared composition")
    members = group["members"]
    if (
        Counter(row["ref"] for row in members)
        != {r["monster_reference"]: r["quantity"] for r in declared}
        or len({row["id"] for row in members}) != len(members)
        or any(
            _native_region(event["map_id"], row) != event["region_id"]
            for row in members
        )
    ):
        raise ValueError(
            "World group differs from its declared environmental population"
        )
    membership = dict(
        entity_kind="group",
        entity_id=group_id,
        reference=group_reference,
        source_key=source_key,
        spawn_owned=False,
    )
    if storage.register_memberships(db, instance_id, [membership]) is False:
        return False
    db.execute(
        "INSERT INTO environmental_event_groups(instance_id,group_id,admitted_revision) "
        "VALUES(%s,%s,%s) ON CONFLICT DO NOTHING",
        (instance_id, group_id, group["revision"]),
    )
    prior = db.execute(
        "SELECT admitted_revision FROM environmental_event_groups WHERE instance_id=%s AND group_id=%s",
        (instance_id, group_id),
    ).fetchone()
    if prior["admitted_revision"] != group["revision"]:
        raise ValueError("Frozen environmental group incarnation changed")
    for row in members:
        db.execute(
            "INSERT INTO environmental_event_group_members VALUES(%s,%s,%s,%s) ON CONFLICT DO NOTHING",
            (instance_id, group_id, row["id"], row["ref"]),
        )
    actual = db.execute(
        "SELECT monster_id,monster_reference FROM environmental_event_group_members "
        "WHERE instance_id=%s AND group_id=%s",
        (instance_id, group_id),
    ).fetchall()
    if {(row["monster_id"], row["monster_reference"]) for row in actual} != {
        (row["id"], row["ref"]) for row in members
    }:
        raise ValueError("Frozen environmental group members changed")
    if profile["family"] == "monster_defeat":
        storage.register_memberships(
            db,
            instance_id,
            [
                dict(
                    entity_kind="monster",
                    entity_id=row["id"],
                    reference=row["ref"],
                    source_key=source_key + ":" + str(row["id"]),
                    spawn_owned=False,
                )
                for row in members
            ],
        )
    return True


def winning_facts(
    db, *, receipt, source_scene, account_id, character_id, occurred_at_ms
):
    """Use the native completed lease plus every frozen original defeated member."""
    from .environmental_gameplay import GameplayFact

    lease = source_scene.get("group_lease")
    if lease is None:
        return ()
    if (
        not isinstance(lease, (tuple, list))
        or len(lease) != 4
        or not isinstance(lease[0], (tuple, list))
        or len(lease[0]) != 3
    ):
        raise ValueError("Invalid admitted environmental group lease")
    key, generation, fight_id, revision = lease
    if (
        tuple(key[:2]) != (source_scene["map_id"], source_scene["instance_id"])
        or not isinstance(generation, str)
        or not generation
        or fight_id != receipt["fight_id"]
    ):
        raise ValueError("Environmental group lease differs from the winning scene")
    rules.integer(revision, "group lease revision", minimum=1)
    occupied = presence.capture(*key[:2])
    if occupied is None:
        return ()
    candidates = db.execute(
        "SELECT g.instance_id,m.reference,e.region_id FROM environmental_event_groups g "
        "JOIN environmental_event_memberships m ON m.instance_id=g.instance_id AND m.entity_id=g.group_id "
        "AND m.entity_kind='group' JOIN environmental_event_instances e ON e.instance_id=g.instance_id "
        "WHERE e.map_id=%s AND e.world_instance_id=%s AND g.group_id=%s AND e.state='active' "
        "AND g.admitted_revision=%s ORDER BY g.instance_id",
        (*key, revision - 1),
    ).fetchall()
    if not candidates:
        return ()
    group = db.execute(
        "SELECT status,revision,members FROM combat_groups WHERE map_id=%s AND instance_id=%s AND group_id=%s",
        tuple(key),
    ).fetchone()
    if (
        group is None
        or group["status"] != "defeated"
        or group["revision"] != revision + 1
    ):
        return ()
    actual = {(row["id"], row["ref"]) for row in group["members"]}
    killed = {tuple(row) for row in receipt["original_monsters"]}
    facts, seen = [], set()
    for event in candidates:
        rows = db.execute(
            "SELECT monster_id,monster_reference FROM environmental_event_group_members "
            "WHERE instance_id=%s AND group_id=%s",
            (event["instance_id"], key[2]),
        ).fetchall()
        expected = {(row["monster_id"], row["monster_reference"]) for row in rows}
        if not expected or expected != actual or not expected.issubset(killed):
            continue
        identity = (event["reference"], event["region_id"])
        if identity in seen:
            continue
        seen.add(identity)
        facts.append(
            GameplayFact(
                "group_defeated",
                f"fight:{fight_id}:group:{key[2]}",
                account_id,
                character_id,
                key[0],
                key[1],
                "group",
                key[2],
                event["reference"],
                occurred_at_ms,
                region_id=event["region_id"],
                fight_id=fight_id,
            )
        )
    return tuple(facts)
