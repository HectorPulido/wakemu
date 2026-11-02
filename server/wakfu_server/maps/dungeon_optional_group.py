"""Source-neutral registration of one pinned native optional fight group."""
from psycopg.types.json import Jsonb


def create(
    db,
    groups,
    run,
    config,
    character,
    *,
    room_order,
    source_order,
    anchor,
    activation,
    rule_sha256,
):
    from wakfu_server import dungeon_runtime_config
    from wakfu_server.combat_terrain import map_geometry
    from wakfu_server.dungeon_encounters import roster_members
    from wakfu_server.npc_actor_identity import allocate_block

    room = next(r for r in config["topology"]["rooms"] if r["order"] == room_order)
    frozen = next(
        r for r in config["compiled_plan"]["rooms"] if r["order"] == room_order
    )
    roster = [
        dict(
            ref_id=r["ref_id"],
            count=r["count"],
            min_level=r["native_min_level"],
            max_level=r["native_max_level"],
            role=r["role"],
        )
        for r in frozen["monsters"]
    ]
    geometry = map_geometry(character["map_id"])
    cells = set(map(tuple, room["cells"]))
    if not cells <= set(map(tuple, geometry["cells"])) or tuple(anchor) not in cells:
        raise ValueError("Optional group anchor leaves its pinned native room")
    section = dict(
        geometry,
        cells=tuple(cells),
        edges=tuple(
            (a, b)
            for a, b in geometry["edges"]
            if tuple(a) in cells and tuple(b) in cells
        ),
    )
    db.execute(
        "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
        (f"monster-population:{character['map_id']}:{run['instance_id']}",),
    )
    group_id = db.execute("SELECT nextval('dungeon_room_group_ids') AS id").fetchone()[
        "id"
    ]
    position = tuple(character[k] for k in ("x", "y", "z"))
    members = roster_members(
        run["instance_id"],
        roster,
        asset_map_id=character["map_id"],
        anchor=anchor,
        geometry=section,
        group_id=group_id,
        select_level=dungeon_runtime_config.level_selector(
            config, room_order=room_order
        ),
        actor_id_base=allocate_block(db, 128),
        occupied=(position,) if position in cells else (),
        player_slots=6,
    )
    groups.register_transaction(
        db, character["map_id"], run["instance_id"], group_id, members
    )
    db.execute(
        "INSERT INTO dungeon_optional_access(instance_id,room_order,source_order,asset_map_id,group_id,account_id,character_id,source_uid,source_reference,action_id,activation_method,target,catalog_hash,rule_sha256,vote_gate_instance_id) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
        (
            run["instance_id"],
            room_order,
            source_order,
            character["map_id"],
            group_id,
            character["account_id"],
            character["id"],
            activation.get("source_uid"),
            activation.get("source_reference"),
            activation["action_id"],
            activation["activation_method"],
            Jsonb(anchor),
            run["catalog_hash"],
            rule_sha256,
            activation.get("vote_gate_instance_id"),
        ),
    )
    db.execute(
        "INSERT INTO dungeon_optional_publication_outbox(instance_id) VALUES(%s)",
        (run["instance_id"],),
    )
    return group_id
