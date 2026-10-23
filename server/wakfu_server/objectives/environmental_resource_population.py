"""Occupied-scope resources owned by a declared environmental event.

Original scenario counts/actions are source authority. Exact placement cells
and catalog_cvF transitions are separately declared server policies. Stage0
publication disables collection; full native spatial removal is not certified.
"""
import secrets

from . import environmental_presence as presence
from . import environmental_runtime as rules


def populate(db, event, *, now_ms):
    from . import environmental_storage as storage
    from wakfu_server.planting_cells import cells

    occupied = presence.capture(event["map_id"], event["world_instance_id"])
    if occupied is None or event["state"] != "active":
        return ()
    storage._transaction(db)
    storage._scope_lock(db, event["map_id"], event["world_instance_id"])
    if not presence.current(occupied, event["map_id"], event["world_instance_id"]):
        return ()
    rules.integer(now_ms, "resource population clock")
    fresh = db.execute(
        "SELECT * FROM environmental_event_instances WHERE instance_id=%s FOR UPDATE",
        (event["instance_id"],),
    ).fetchone()
    if fresh is None or (fresh["map_id"], fresh["world_instance_id"]) != (
        event["map_id"],
        event["world_instance_id"],
    ):
        raise ValueError("Environmental resource event scope changed")
    event = fresh
    if (
        event["state"] != "active"
        or not event["started_at_ms"] <= now_ms < event["deadline_ms"]
    ):
        return ()
    policy = db.execute(
        "SELECT * FROM environmental_profile_resource_population WHERE profile_key=%s AND version=%s",
        (event["profile_key"], event["version"]),
    ).fetchone()
    if policy is None:
        return ()
    if (
        db.execute(
            "SELECT 1 FROM environmental_owned_resources WHERE instance_id=%s LIMIT 1",
            (event["instance_id"],),
        ).fetchone()
        is not None
    ):
        return ()  # A depleted member is never regenerated during this event.
    profile = storage._event_profile(db, event)
    if not profile["enabled"]:
        return ()
    from .environmental_resource_stage import resolve

    source = resolve(db, policy["source_key"], profile["native_scenario_id"])
    location = db.execute(
        "SELECT 1 FROM environmental_native_scenario_locations WHERE source_key=%s "
        "AND scenario_id=%s AND map_id=%s AND region_id=%s AND native_cells_present LIMIT 1",
        (
            policy["source_key"],
            profile["native_scenario_id"],
            event["map_id"],
            event["region_id"],
        ),
    ).fetchone()
    if source is None or location is None or profile["family"] != "resource_collect":
        raise ValueError(
            "Environmental resource population lacks its original action/location"
        )
    action = source["original_action"]
    if (
        action["profession_id"] != 0
        or action["item_reference"] != 0
        or action["product_references"]
        or action["raw_getters"]["cvF"] != 0
    ):
        raise ValueError(
            "Original environmental resource action requires additional policy authority"
        )
    from wakfu_server.resource_action_criteria import minimum_effective_level

    minimum_effective_level(action["criteria"])
    objectives = storage._objectives(db, profile)
    matching_objectives = [
        row
        for row in objectives
        if row["target_reference"] == source["resource_reference"]
        and row["action_id"] == source["action_id"]
        and row["resource_step"] == source["native_step"]
    ]
    if not matching_objectives:
        raise ValueError(
            "Environmental resource objective differs from its original action"
        )
    raw = db.execute(
        "SELECT native_value FROM environmental_native_configuration WHERE source_key=%s "
        "AND scenario_id=%s AND normalized_key='ressourcequantitytospawn'",
        (policy["source_key"], profile["native_scenario_id"]),
    ).fetchall()
    if len(raw) != 1 or not raw[0]["native_value"].isdigit():
        raise ValueError("Missing original environmental resource population size")
    quantity = int(raw[0]["native_value"])
    rules.integer(quantity, "resource population", minimum=1)
    if quantity > 4096:
        raise ValueError(
            "Environmental resource population exceeds its bounded producer"
        )
    candidates = db.execute(
        "SELECT x,y,z,ordinal FROM environmental_profile_resource_cells "
        "WHERE profile_key=%s AND version=%s ORDER BY ordinal",
        (event["profile_key"], event["version"]),
    ).fetchall()
    native = cells(event["map_id"])
    if not candidates or any(
        not any(
            r["z"] == c["z"] and r["region_id"] == event["region_id"]
            for r in native.get((c["x"], c["y"]), ())
        )
        for c in candidates
    ):
        raise ValueError(
            "Declared environmental placement is not an exact native territory surface"
        )
    taken = {
        (r["x"], r["y"])
        for r in db.execute(
            "SELECT x,y FROM planted_resources WHERE map_id=%s AND instance_id=%s",
            (event["map_id"], event["world_instance_id"]),
        ).fetchall()
    }
    # One scalar scan only when a new event population is created; never a
    # per-tick world snapshot or an empty-map simulation.
    world = occupied[0]
    with world.lock:
        origins = tuple(
            (c["x"], c["y"], c["z"])
            for _, _, c in world.players.values()
            if world.location(c) == (event["map_id"], event["world_instance_id"])
        )
        taken.update(
            (c["x"], c["y"])
            for _, _, c in world.players.values()
            if world.location(c) == (event["map_id"], event["world_instance_id"])
        )
    from wakfu_server.monster_population_capacity import physical_cells
    from .environmental_random_rosters import _scene_cells

    taken.update(
        point[:2]
        for point in physical_cells(db, event["map_id"], event["world_instance_id"])
    )
    taken.update(_scene_cells(db, event["map_id"], event["world_instance_id"]))
    for table in ("mining_vein_slots", "fishing_spot_slots"):
        taken.update(
            (r["x"], r["y"])
            for r in db.execute(
                f"SELECT x,y FROM {table} WHERE map_id=%s AND instance_id=%s AND enabled",
                (event["map_id"], event["world_instance_id"]),
            ).fetchall()
        )
    taken.update(
        (r["x"], r["y"])
        for r in db.execute(
            "SELECT r.x,r.y FROM environmental_resource_publications p JOIN environmental_owned_resources r USING(resource_uid) "
            "WHERE r.map_id=%s AND r.world_instance_id=%s AND p.published_at_ms IS NULL AND p.superseded_at_ms IS NULL",
            (event["map_id"], event["world_instance_id"]),
        ).fetchall()
    )
    taken.update(
        (r["resource"]["x"], r["resource"]["y"])
        for r in db.execute(
            "SELECT resource FROM planting_growth_outbox WHERE NOT published AND (resource->>'map_id')::integer=%s "
            "AND (resource->>'instance_id')::bigint=%s",
            (event["map_id"], event["world_instance_id"]),
        ).fetchall()
    )
    from wakfu_server.combat_terrain import map_geometry
    from .environmental_resource_placement import POLICY, plan

    # Sealed rows above still attest the original scenario territory. The old
    # generated list was a lexicographic prefix, not the complete zone. This
    # declared v2 policy derives positions from that same original territory's
    # full native surfaces, intersected with actual reachable walk geometry.
    placement = plan(
        native,
        map_geometry(event["map_id"]),
        region_id=event["region_id"],
        origins=origins,
        taken=taken,
        quantity=quantity,
        seed=f"{POLICY}:{event['instance_id']}:{event['profile_key']}:{event['version']}",
    )
    available = []
    for cell in placement:
        if (cell["x"], cell["y"]) in taken:
            continue
        key = f"planting-cell:{event['map_id']}:{event['world_instance_id']}:{cell['x']}:{cell['y']}"
        # Ordinary planting owns this same cell lock before inserting and then
        # contributing to the event. Never wait on its cell while holding the
        # event scope; skipping busy cells avoids reversing that lock order.
        if not db.execute(
            "SELECT pg_try_advisory_xact_lock(hashtextextended(%s,0)) AS held", (key,)
        ).fetchone()["held"]:
            continue
        if (
            db.execute(
                "SELECT 1 FROM planted_resources WHERE map_id=%s AND instance_id=%s AND x=%s AND y=%s",
                (event["map_id"], event["world_instance_id"], cell["x"], cell["y"]),
            ).fetchone()
            is not None
        ):
            continue
        available.append(cell)
        if len(available) == quantity:
            break
    # Preserve the original objective and rewards. A small zone may have less
    # capacity than the decorative spawn quota, but must still allow completion.
    minimum = max(row["required_quantity"] for row in matching_objectives)
    if len(available) < minimum or not presence.current(
        occupied, event["map_id"], event["world_instance_id"]
    ):
        return ()
    spawned = []
    for cell in available:
        uid = secrets.randbits(62) + 1
        db.execute(
            "INSERT INTO planted_resources "
            "(resource_uid,map_id,instance_id,x,y,z,resource_reference,stage,creation_time) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                uid,
                event["map_id"],
                event["world_instance_id"],
                cell["x"],
                cell["y"],
                cell["z"],
                source["resource_reference"],
                source["native_step"],
                now_ms,
            ),
        )
        storage.register_memberships(
            db,
            event["instance_id"],
            [
                dict(
                    entity_kind="resource",
                    entity_id=uid,
                    reference=source["resource_reference"],
                    source_key=f"event-resource:{event['instance_id']}:{cell['ordinal']}:{POLICY}",
                    spawn_owned=True,
                )
            ],
        )
        db.execute(
            "INSERT INTO environmental_owned_resources "
            "(instance_id,resource_uid,map_id,world_instance_id,x,y,z,reference,native_step,creation_time,spawned_at_ms) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                event["instance_id"],
                uid,
                event["map_id"],
                event["world_instance_id"],
                cell["x"],
                cell["y"],
                cell["z"],
                source["resource_reference"],
                source["native_step"],
                now_ms,
                now_ms,
            ),
        )
        db.execute(
            "INSERT INTO environmental_resource_publications(resource_uid,stage,created_at_ms) VALUES(%s,%s,%s)",
            (uid, source["native_step"], now_ms),
        )
        spawned.append(uid)
    return tuple(spawned)


def assert_cell_available(db, *, map_id, instance_id, x, y):
    """The ordinary planter already owns the shared planting-cell lock.

    Keep that cell reserved until its last environmental packet is published;
    otherwise a delayed stage0 could disable a newer player's resource.
    """
    if presence.capture(map_id, instance_id) is None:
        return
    if (
        db.execute(
            "SELECT 1 FROM environmental_resource_publications p "
            "JOIN environmental_owned_resources r USING(resource_uid) WHERE r.map_id=%s AND r.world_instance_id=%s "
            "AND r.x=%s AND r.y=%s AND p.published_at_ms IS NULL AND p.superseded_at_ms IS NULL LIMIT 1",
            (map_id, instance_id, x, y),
        ).fetchone()
        is not None
    ):
        raise ValueError("Environmental publication still reserves this planting cell")


def retire(db, resource_uid, *, now_ms, reason):
    from . import environmental_storage as storage

    rules.integer(resource_uid, "owned resource", minimum=1)
    rules.integer(now_ms, "resource retirement clock")
    if reason not in ("interaction", "cleanup"):
        raise ValueError("Unknown environmental resource retirement reason")
    storage._transaction(db)
    owned = db.execute(
        "SELECT * FROM environmental_owned_resources WHERE resource_uid=%s",
        (resource_uid,),
    ).fetchone()
    if owned is None:
        raise ValueError("Resource is not an owned environmental population member")
    occupied = presence.capture(owned["map_id"], owned["world_instance_id"])
    if occupied is None:
        return False
    storage._scope_lock(db, owned["map_id"], owned["world_instance_id"])
    if not presence.current(occupied, owned["map_id"], owned["world_instance_id"]):
        return False
    owned = db.execute(
        "SELECT * FROM environmental_owned_resources WHERE resource_uid=%s FOR UPDATE",
        (resource_uid,),
    ).fetchone()
    if owned["retired_at_ms"] is not None:
        return False
    event = db.execute(
        "SELECT state FROM environmental_event_instances WHERE instance_id=%s",
        (owned["instance_id"],),
    ).fetchone()
    if (reason == "interaction" and event["state"] != "active") or (
        reason == "cleanup"
        and event["state"] not in ("completed", "expired", "cancelled")
    ):
        raise ValueError("Environmental retirement does not match its event lifecycle")
    physical = db.execute(
        "SELECT * FROM planted_resources WHERE resource_uid=%s FOR UPDATE",
        (resource_uid,),
    ).fetchone()
    if physical is not None:
        if (
            physical["map_id"],
            physical["instance_id"],
            physical["x"],
            physical["y"],
            physical["z"],
            physical["resource_reference"],
            physical["stage"],
            physical["creation_time"],
        ) != (
            owned["map_id"],
            owned["world_instance_id"],
            owned["x"],
            owned["y"],
            owned["z"],
            owned["reference"],
            owned["native_step"],
            owned["creation_time"],
        ):
            raise ValueError("Environmental owned resource identity changed")
        db.execute(
            "DELETE FROM planted_resources WHERE resource_uid=%s", (resource_uid,)
        )
    db.execute(
        "UPDATE environmental_owned_resources SET retired_at_ms=%s,retirement_reason=%s WHERE resource_uid=%s",
        (now_ms, reason, resource_uid),
    )
    db.execute(
        "UPDATE environmental_resource_publications SET superseded_at_ms=%s "
        "WHERE resource_uid=%s AND published_at_ms IS NULL AND superseded_at_ms IS NULL",
        (now_ms, resource_uid),
    )
    if physical is not None:
        db.execute(
            "INSERT INTO environmental_resource_publications(resource_uid,stage,created_at_ms) VALUES(%s,0,%s)",
            (resource_uid, now_ms),
        )
    return True


def cleanup(db, *, map_id, instance_id, now_ms, limit=128):
    from . import environmental_storage as storage

    occupied = presence.capture(map_id, instance_id)
    if occupied is None:
        return ()
    rules.integer(limit, "owned resource cleanup batch", minimum=1)
    if limit > 1024:
        raise ValueError("Environmental owned resource cleanup exceeds its bound")
    storage._transaction(db)
    storage._scope_lock(db, map_id, instance_id)
    if not presence.current(occupied, map_id, instance_id):
        return ()
    rows = db.execute(
        "SELECT c.* FROM environmental_cleanup_outbox c JOIN environmental_event_instances e USING(instance_id) "
        "WHERE e.map_id=%s AND e.world_instance_id=%s AND e.state IN ('completed','expired','cancelled') "
        "AND c.entity_kind='resource' AND c.action='despawn_owned' AND c.completed_at_ms IS NULL "
        "AND EXISTS(SELECT 1 FROM environmental_owned_resources r WHERE r.resource_uid=c.entity_id AND r.instance_id=c.instance_id) "
        "ORDER BY c.instance_id,c.entity_id LIMIT %s FOR UPDATE OF c SKIP LOCKED",
        (map_id, instance_id, limit),
    ).fetchall()
    completed = []
    for row in rows:
        prior = db.execute(
            "SELECT retired_at_ms FROM environmental_owned_resources WHERE resource_uid=%s",
            (row["entity_id"],),
        ).fetchone()
        if prior["retired_at_ms"] is None and not retire(
            db, row["entity_id"], now_ms=now_ms, reason="cleanup"
        ):
            continue
        if not presence.current(occupied, map_id, instance_id):
            break
        db.execute(
            "UPDATE environmental_cleanup_outbox SET completed_at_ms=%s WHERE instance_id=%s AND entity_kind=%s AND entity_id=%s",
            (now_ms, row["instance_id"], row["entity_kind"], row["entity_id"]),
        )
        completed.append(row["entity_id"])
    return tuple(completed)


def pending_publications(db, *, map_id, instance_id, now_ms, limit=256):
    from . import environmental_storage as storage
    from wakfu_server.planting import resource_packet
    from wakfu_server.planting_runtime import state_packet

    occupied = presence.capture(map_id, instance_id)
    if occupied is None:
        return ()
    rules.integer(limit, "resource publication batch", minimum=1)
    if limit > 1024:
        raise ValueError("Environmental resource publication exceeds its bound")
    storage._transaction(db)
    storage._scope_lock(db, map_id, instance_id)
    if not presence.current(occupied, map_id, instance_id):
        return ()
    rows = db.execute(
        "SELECT p.publication_id,p.stage,r.* FROM environmental_resource_publications p "
        "JOIN environmental_owned_resources r USING(resource_uid) WHERE r.map_id=%s AND r.world_instance_id=%s "
        "AND p.published_at_ms IS NULL AND p.superseded_at_ms IS NULL "
        "ORDER BY p.publication_id LIMIT %s FOR UPDATE OF p",
        (map_id, instance_id, limit),
    ).fetchall()
    deliveries = []
    for row in rows:
        physical = db.execute(
            "SELECT resource_uid,resource_reference,stage FROM planted_resources "
            "WHERE map_id=%s AND instance_id=%s AND x=%s AND y=%s",
            (map_id, instance_id, row["x"], row["y"]),
        ).fetchone()
        stale = (row["stage"] == 0 and physical is not None) or (
            row["stage"] != 0
            and (
                row["retired_at_ms"] is not None
                or physical is None
                or (
                    physical["resource_uid"],
                    physical["resource_reference"],
                    physical["stage"],
                )
                != (row["resource_uid"], row["reference"], row["stage"])
            )
        )
        if stale:
            # A delayed stage0 must never disable a newer player crop at XY.
            db.execute(
                "UPDATE environmental_resource_publications SET superseded_at_ms=%s WHERE publication_id=%s",
                (now_ms, row["publication_id"]),
            )
            continue
        resource = dict(
            row, instance_id=instance_id, resource_reference=row["reference"]
        )
        packet = (
            state_packet(resource, 0)
            if row["stage"] == 0
            else resource_packet(resource)
        )
        deliveries.append(dict(publication_id=row["publication_id"], packets=(packet,)))
    return tuple(deliveries)


def acknowledge(db, *, map_id, instance_id, publication_ids, now_ms):
    from . import environmental_storage as storage

    occupied = presence.capture(map_id, instance_id)
    if occupied is None or not publication_ids:
        return 0
    storage._transaction(db)
    storage._scope_lock(db, map_id, instance_id)
    if not presence.current(occupied, map_id, instance_id):
        return 0
    return db.execute(
        "UPDATE environmental_resource_publications p SET published_at_ms=%s "
        "FROM environmental_owned_resources r WHERE r.resource_uid=p.resource_uid AND r.map_id=%s "
        "AND r.world_instance_id=%s AND p.publication_id=ANY(%s) AND p.published_at_ms IS NULL "
        "AND p.superseded_at_ms IS NULL",
        (now_ms, map_id, instance_id, list(publication_ids)),
    ).rowcount
