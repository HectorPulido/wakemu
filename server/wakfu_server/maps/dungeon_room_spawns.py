"""Register each frozen dungeon room once, sharing its durable transaction."""
from wakfu_server.dungeon_encounters import room_members


def ensure_room_group(
    db,
    groups,
    instance_id,
    *,
    asset_map_id,
    anchor,
    geometry,
    select_level,
    occupied=(),
    player_slots=6,
):
    """Replay the existing room group; defeat retries reuse its available group.

    The run lock serializes entry, reconnect and settlement handoffs. Receipt and
    combat group registration commit together; native publication is external.
    """
    run = db.execute(
        "SELECT * FROM dungeon_room_runs WHERE instance_id=%s FOR UPDATE",
        (instance_id,),
    ).fetchone()
    if run is None:
        raise ValueError("Dungeon run is not initialized")
    if run["status"] == "completed":
        return None
    if run["status"] != "active":
        raise ValueError("Dungeon run is not active")
    receipt = db.execute(
        "SELECT * FROM dungeon_room_spawn_receipts WHERE instance_id=%s AND room_order=%s",
        (instance_id, run["current_room"]),
    ).fetchone()
    if receipt is not None:
        if receipt["asset_map_id"] != asset_map_id:
            raise ValueError("Dungeon room asset identity changed")
        db.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
            (f"monster-population:{asset_map_id}:{instance_id}",),
        )
        row = db.execute(
            "SELECT members,status FROM combat_groups WHERE map_id=%s AND instance_id=%s AND group_id=%s FOR UPDATE",
            (asset_map_id, instance_id, receipt["group_id"]),
        ).fetchone()
        if row is None:
            raise ValueError("Dungeon room receipt lacks its registered group")
        from .npc_actor_identity import repair_available_dungeon_members

        members = repair_available_dungeon_members(
            db, (asset_map_id, instance_id, receipt["group_id"]), row
        )
        return dict(receipt, members=members, status=row["status"], replay=True)
    group_id = db.execute("SELECT nextval('dungeon_room_group_ids') AS id").fetchone()[
        "id"
    ]
    from .npc_actor_identity import allocate_block

    members = room_members(
        run,
        asset_map_id=asset_map_id,
        anchor=anchor,
        geometry=geometry,
        group_id=group_id,
        actor_id_base=allocate_block(db, 128),
        select_level=select_level,
        occupied=occupied,
        player_slots=player_slots,
    )
    groups.register_transaction(db, asset_map_id, instance_id, group_id, members)
    receipt = db.execute(
        "INSERT INTO dungeon_room_spawn_receipts(instance_id,room_order,asset_map_id,group_id) "
        "VALUES(%s,%s,%s,%s) RETURNING *",
        (instance_id, run["current_room"], asset_map_id, group_id),
    ).fetchone()
    return dict(receipt, members=members, status="available", replay=False)
