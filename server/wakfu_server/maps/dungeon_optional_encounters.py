"""Independent optional encounter authority; mandatory progress is read-only."""
import json
from wakfu_server.dungeon_optional_checkpoint import require_access


def optional_scope(encounter):
    return encounter.get("encounter_scope", "main") == "optional"


def group_receipt(db, group_key, *, lock=False):
    return db.execute(
        "SELECT * FROM dungeon_optional_access WHERE asset_map_id=%s "
        "AND instance_id=%s AND group_id=%s" + (" FOR UPDATE" if lock else ""),
        group_key,
    ).fetchone()


def lock_group_run(db, group_key):
    """Optional-only fight creation preflight, before account/session locks."""
    receipt = group_receipt(db, group_key)
    if receipt is None:
        return None
    run = db.execute(
        "SELECT * FROM dungeon_room_runs WHERE instance_id=%s FOR UPDATE",
        (receipt["instance_id"],),
    ).fetchone()
    if run is None:
        raise ValueError("Optional fight lost its mandatory run")
    require_access(db, run, receipt)
    return run["instance_id"]


def bind(
    db,
    run,
    receipt,
    character_id,
    fight_id,
    *,
    player_team,
    expected_selection_revision=None
):
    """Caller holds main-run lock before optional/group locks."""
    require_access(db, run, receipt)
    if receipt["status"] not in ("available", "active"):
        raise ValueError("Optional encounter requires completed main progression")
    if type(player_team) is not int or player_team not in (0, 1):
        raise ValueError("Invalid optional encounter player team")
    member = db.execute(
        "SELECT 1 FROM dungeon_instance_members m JOIN dungeon_instances i USING(instance_id) "
        "WHERE m.instance_id=%s AND m.party_id=%s AND m.character_id=%s "
        "AND m.status='active' AND i.status='active'",
        (receipt["instance_id"], run["party_id"], character_id),
    ).fetchone()
    participant = db.execute(
        "SELECT team FROM combat_fight_participants WHERE fight_id=%s AND character_id=%s",
        (fight_id, character_id),
    ).fetchone()
    if member is None or participant is None or participant["team"] != player_team:
        raise ValueError("Optional actor is not an authorized encounter participant")
    old = db.execute(
        "SELECT * FROM dungeon_room_encounters WHERE fight_id=%s", (fight_id,)
    ).fetchone()
    if old is not None:
        if not optional_scope(old) or any(
            old[k] != v
            for k, v in (
                ("instance_id", receipt["instance_id"]),
                ("room_order", receipt["room_order"]),
                ("player_team", player_team),
            )
        ):
            raise ValueError("Conflicting optional encounter replay")
        return old
    if receipt["status"] != "available":
        raise ValueError("Optional encounter is already active")
    db.execute(
        "INSERT INTO dungeon_room_encounters(fight_id,instance_id,room_order,player_team,"
        "encounter_scope,optional_instance_id) VALUES(%s,%s,%s,%s,'optional',%s)",
        (
            fight_id,
            receipt["instance_id"],
            receipt["room_order"],
            player_team,
            receipt["instance_id"],
        ),
    )
    from wakfu_server import dungeon_difficulty

    dungeon_difficulty.freeze_encounter(
        db,
        receipt["instance_id"],
        fight_id,
        expected_selection_revision=expected_selection_revision,
    )
    # Main-boss stele selection is deliberately not inherited by this branch.
    db.execute(
        "UPDATE dungeon_optional_access SET status='active' WHERE instance_id=%s",
        (receipt["instance_id"],),
    )
    return db.execute(
        "SELECT * FROM dungeon_room_encounters WHERE fight_id=%s", (fight_id,)
    ).fetchone()


def settle(db, run, encounter, fight):
    receipt = db.execute(
        "SELECT * FROM dungeon_optional_access WHERE instance_id=%s FOR UPDATE",
        (run["instance_id"],),
    ).fetchone()
    if receipt is None or receipt["room_order"] != encounter["room_order"]:
        raise ValueError("Optional result lacks its completed-main access receipt")
    require_access(db, run, receipt)
    if receipt["status"] != "active":
        raise ValueError("Optional access is not active")
    victory = fight.winner == encounter["player_team"]
    revision = receipt["revision"] + 1
    result = dict(
        instance_id=run["instance_id"],
        current_room=run["current_room"],
        completed=run["status"] == "completed",
        revision=run["revision"],
        victory=victory,
        encounter_scope="optional",
        optional_room=receipt["room_order"],
        optional_revision=revision,
    )
    db.execute(
        "UPDATE dungeon_optional_access SET status=%s,revision=%s WHERE instance_id=%s",
        ("victory" if victory else "available", revision, run["instance_id"]),
    )
    db.execute(
        "UPDATE dungeon_room_encounters SET status=%s,result_revision=%s,result=%s::jsonb WHERE fight_id=%s",
        ("victory" if victory else "defeat", revision, json.dumps(result), fight.id),
    )
    return dict(result, replay=False)


def abort(db, run, encounter):
    receipt = db.execute(
        "SELECT * FROM dungeon_optional_access WHERE instance_id=%s FOR UPDATE",
        (run["instance_id"],),
    ).fetchone()
    if receipt is None or receipt["status"] != "active":
        raise ValueError("Optional abort lacks its active receipt")
    require_access(db, run, receipt)
    result = dict(
        instance_id=run["instance_id"],
        current_room=run["current_room"],
        revision=run["revision"],
        completed=run["status"] == "completed",
        aborted=True,
        encounter_scope="optional",
        optional_room=receipt["room_order"],
    )
    db.execute(
        "UPDATE dungeon_optional_access SET status='available' WHERE instance_id=%s",
        (run["instance_id"],),
    )
    db.execute(
        "UPDATE dungeon_room_encounters SET status='aborted',result_revision=%s,result=%s::jsonb WHERE fight_id=%s",
        (receipt["revision"], json.dumps(result), encounter["fight_id"]),
    )
    return dict(result, replay=False)


def combat_cells(db, group_key, config, progress, participants):
    receipt = group_receipt(db, group_key)
    if receipt is None:
        return None
    require_access(db, progress, receipt)
    if receipt["status"] not in ("available", "active"):
        raise ValueError("Optional combat requires its available receipt")
    if receipt["catalog_hash"] != config["compiled_plan"]["document_sha256"]:
        raise ValueError("Optional encounter configuration changed")
    matches = [
        r for r in config["topology"]["rooms"] if r["order"] == receipt["room_order"]
    ]
    if len(matches) != 1:
        raise ValueError("Optional combat terrain is absent")
    cells = frozenset(map(tuple, matches[0]["cells"]))
    if not cells or any(tuple(p) not in cells for p in participants):
        raise ValueError("Optional combat participant is outside native terrain")
    return cells


def publish_native_scene(world, map_id, instance_id, opcode, payload):
    """Confirm writes through the existing World native sender; retry on failure."""
    with world.lock:
        peers = [
            peer
            for _, peer, actor in world.players.values()
            if world.location(actor) == (map_id, instance_id)
        ]
        delivered = [world._send(peer, opcode, payload) for peer in peers]
        return bool(delivered) and all(delivered)


def publish_pending(store, groups, *, instance_id, publish):
    """Replay committed publication; failures retain the durable pending row.

    The normal group claim lock prevents a local attack racing the snapshot.
    Packet replay uses the same persistent native actor/group IDs, as ordinary
    reconnect hydration does. No inventory or access mutation occurs here.
    """
    with groups.lock:
        with store.connection() as db:
            row = db.execute(
                "SELECT a.*,g.members,g.status group_status FROM dungeon_optional_publication_outbox o "
                "JOIN dungeon_optional_access a USING(instance_id) JOIN dungeon_instances i USING(instance_id) "
                "JOIN dungeon_room_runs r USING(instance_id) JOIN combat_groups g "
                "ON g.map_id=a.asset_map_id AND g.instance_id=a.instance_id AND g.group_id=a.group_id "
                "WHERE o.instance_id=%s AND NOT o.published AND i.status='active' "
                "AND (r.status='completed' OR (r.status='active' AND a.activation_method='native_vote'))",
                (instance_id,),
            ).fetchone()
            if row is not None and row.get("activation_method") == "native_vote":
                run = db.execute(
                    "SELECT * FROM dungeon_room_runs WHERE instance_id=%s",
                    (instance_id,),
                ).fetchone()
                require_access(db, run, row)
        if (
            row is None
            or row["status"] != "available"
            or row["group_status"] != "available"
        ):
            return False
        from wakfu_server.combat_monster_world import spawn_group

        delivered = publish(
            row["asset_map_id"],
            instance_id,
            12608,
            spawn_group(
                groups._members(dict(members=row["members"], instance_id=instance_id)),
                group_id=row["group_id"],
            ),
        )
        # WORLD.emit_location normally returns None. An explicit False from a
        # delivery adapter is failure, not permission to acknowledge the row.
        if delivered is False:
            return False
        with store.connection() as db:
            db.execute(
                "UPDATE dungeon_optional_publication_outbox SET published=true WHERE instance_id=%s",
                (instance_id,),
            )
        return True
