"""Bind selected durable room groups without changing combat execution."""
from wakfu_server.dungeon_progression import bind_encounter


def bind_room_group(db, group_key, character_id, fight_id, *, player_team=0):
    """Run inside fight creation after its durable participant is inserted.

    Ordinary map groups do not acquire a dungeon binding. A dungeon run only
    admits its current room receipt, never a developer-created incidental group.
    The caller owns transaction commit and subsequent combat registration.
    """
    if (
        not isinstance(group_key, tuple)
        or len(group_key) != 3
        or any(type(value) is not int for value in group_key)
    ):
        raise ValueError("Invalid dungeon combat group identity")
    map_id, instance_id, group_id = group_key
    if instance_id == 0:
        return None
    run = db.execute(
        "SELECT party_id,current_room,status FROM dungeon_room_runs "
        "WHERE instance_id=%s FOR UPDATE",
        (instance_id,),
    ).fetchone()
    if run is None:
        return None
    if run["status"] != "active":
        raise ValueError("Dungeon run is not active")
    receipt = db.execute(
        "SELECT asset_map_id,group_id FROM dungeon_room_spawn_receipts "
        "WHERE instance_id=%s AND room_order=%s",
        (instance_id, run["current_room"]),
    ).fetchone()
    if (
        receipt is None
        or receipt["asset_map_id"] != map_id
        or receipt["group_id"] != group_id
    ):
        raise ValueError("Combat group is not the current dungeon room")
    reconcile_aborted_encounters(db, instance_id=instance_id)
    return bind_encounter(
        db,
        instance_id,
        run["party_id"],
        character_id,
        fight_id,
        player_team=player_team,
    )


def abort_room_encounter(db, fight_id):
    """Keep an aborted receipt without advancing the room or run revision.

    Called after an authorized fight abort in the same database transaction.
    The terminal receipt frees the one-active-encounter constraint for retry.
    """
    import json

    encounter = db.execute(
        "SELECT * FROM dungeon_room_encounters WHERE fight_id=%s",
        (fight_id,),
    ).fetchone()
    if encounter is None:
        return None
    fight = db.execute(
        "SELECT status FROM combat_fights WHERE id=%s", (fight_id,)
    ).fetchone()
    if fight is None or fight["status"] != "aborted":
        raise ValueError("Dungeon cleanup requires an aborted durable fight")
    run = db.execute(
        "SELECT * FROM dungeon_room_runs WHERE instance_id=%s FOR UPDATE",
        (encounter["instance_id"],),
    ).fetchone()
    encounter = db.execute(
        "SELECT * FROM dungeon_room_encounters WHERE fight_id=%s FOR UPDATE",
        (fight_id,),
    ).fetchone()
    if encounter["status"] == "aborted":
        return dict(encounter["result"], replay=True)
    if encounter["status"] != "active":
        raise ValueError("Settled dungeon encounter cannot be aborted")
    if (
        run is None
        or run["current_room"] != encounter["room_order"]
        or run["status"] != "active"
    ):
        raise ValueError("Aborted encounter does not belong to the current room")
    result = dict(
        instance_id=run["instance_id"],
        current_room=run["current_room"],
        revision=run["revision"],
        completed=False,
        aborted=True,
    )
    db.execute(
        "UPDATE dungeon_room_encounters SET status='aborted',result_revision=%s,"
        "result=%s::jsonb WHERE fight_id=%s",
        (run["revision"], json.dumps(result), fight_id),
    )
    return dict(result, replay=False)


def reconcile_aborted_encounters(db, *, instance_id=None):
    """Reconcile only durable combat aborts left by startup recovery.

    Call after combat recovery commits its aborted statuses. Live fights and
    previously settled room receipts are excluded. The caller owns commit.
    """
    query = (
        "SELECT e.fight_id FROM dungeon_room_encounters e "
        "JOIN combat_fights f ON f.id=e.fight_id "
        "WHERE e.status='active' AND f.status='aborted' "
    )
    params = ()
    if instance_id is not None:
        if type(instance_id) is not int or instance_id <= 0:
            raise ValueError("Invalid dungeon reconciliation instance")
        query += "AND e.instance_id=%s "
        params = (instance_id,)
    rows = tuple(db.execute(query + "ORDER BY e.instance_id,e.fight_id", params))
    return tuple(abort_room_encounter(db, row["fight_id"]) for row in rows)
