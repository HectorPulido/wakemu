"""Independent postboss encounter nodes; completed primary progress is read-only.

PRIVATE REVIEW COPY. Callers must integrate the run-first transaction boundary,
scope dispatch, hydration, movement admission and native publication before use.
No helper updates dungeon_room_runs or performs a primary/boss reward settlement.
"""
import json

ACCESS = "qualified_native_postboss_route"


def postboss_scope(encounter):
    return encounter.get("encounter_scope", "main") == "postboss"


def policy_nodes(config):
    optional = config["topology"].get("optional_room_policy", {})
    records = [
        r
        for r in optional.get("optional_rooms", [])
        if r.get("access", {}).get("status") == ACCESS
    ]
    source_ids = [r.get("source_order") for r in records]
    orders = [r.get("order") for r in records]
    main = optional.get("main_room_orders", [])
    main_sources = optional.get("main_source_orders", [])
    if (
        any(type(n) is not int or n <= 0 for n in source_ids + orders)
        or len(set(source_ids)) != len(source_ids)
        or len(set(orders)) != len(orders)
        or records
        and (
            not main
            or any(n in main for n in orders)
            or not main_sources
            or any(n in main_sources for n in source_ids)
        )
    ):
        raise ValueError("Ambiguous postboss node identities")
    for record in records:
        terrain = [
            r for r in config["topology"]["rooms"] if r["order"] == record["order"]
        ]
        rosters = [
            r for r in config["compiled_plan"]["rooms"] if r["order"] == record["order"]
        ]
        if (
            len(terrain) != 1
            or len(rosters) != 1
            or terrain[0].get("source_order") != record["source_order"]
            or rosters[0].get("source_order") != record["source_order"]
        ):
            raise ValueError("Postboss policy does not bind its frozen source node")
    return tuple(records)


def group_receipt(db, group_key, *, lock=False):
    return db.execute(
        "SELECT * FROM dungeon_postboss_nodes WHERE asset_map_id=%s "
        "AND instance_id=%s AND group_id=%s" + (" FOR UPDATE" if lock else ""),
        group_key,
    ).fetchone()


def lock_group_run(db, group_key):
    """Preflight before account/session locks; never lock node before run."""
    receipt = group_receipt(db, group_key)
    if receipt is None:
        return None
    run = db.execute(
        "SELECT * FROM dungeon_room_runs WHERE instance_id=%s FOR UPDATE",
        (receipt["instance_id"],),
    ).fetchone()
    _completed(run, receipt["instance_id"])
    return run["instance_id"]


def _completed(run, instance_id):
    if run is None or run["instance_id"] != instance_id or run["status"] != "completed":
        raise ValueError("Postboss access requires its completed primary run")


def _receipt(db, instance_id, source_order, *, lock=True):
    row = db.execute(
        "SELECT * FROM dungeon_postboss_nodes WHERE instance_id=%s AND source_order=%s"
        + (" FOR UPDATE" if lock else ""),
        (instance_id, source_order),
    ).fetchone()
    if row is None:
        raise ValueError("Postboss encounter lacks its independent node receipt")
    return row


def bind(
    db,
    run,
    receipt,
    character_id,
    fight_id,
    *,
    player_team,
    expected_selection_revision=None,
):
    """Caller holds run before group/account locks; re-read node under lock."""
    _completed(run, receipt["instance_id"])
    if type(player_team) is not int or player_team not in (0, 1):
        raise ValueError("Invalid postboss player team")
    receipt = _receipt(db, run["instance_id"], receipt["source_order"])
    if receipt["catalog_hash"] != run["catalog_hash"]:
        raise ValueError("Postboss receipt differs from the frozen primary run")
    member = db.execute(
        "SELECT 1 FROM dungeon_instance_members m JOIN dungeon_instances i USING(instance_id) "
        "WHERE m.instance_id=%s AND m.party_id=%s AND m.character_id=%s "
        "AND m.status='active' AND i.status='active'",
        (run["instance_id"], run["party_id"], character_id),
    ).fetchone()
    participant = db.execute(
        "SELECT team FROM combat_fight_participants WHERE fight_id=%s AND character_id=%s",
        (fight_id, character_id),
    ).fetchone()
    if member is None or participant is None or participant["team"] != player_team:
        raise ValueError("Postboss actor is not an authorized encounter participant")
    old = db.execute(
        "SELECT * FROM dungeon_room_encounters WHERE fight_id=%s", (fight_id,)
    ).fetchone()
    if old is not None:
        if not postboss_scope(old) or any(
            old[k] != v
            for k, v in (
                ("instance_id", run["instance_id"]),
                ("room_order", receipt["room_order"]),
                ("postboss_source_order", receipt["source_order"]),
                ("player_team", player_team),
            )
        ):
            raise ValueError("Conflicting postboss encounter replay")
        return old
    if receipt["status"] != "available" or receipt["active_fight_id"] is not None:
        raise ValueError("Postboss node is not available")
    db.execute(
        "INSERT INTO dungeon_room_encounters(fight_id,instance_id,room_order,player_team,"
        "encounter_scope,optional_instance_id,postboss_source_order) "
        "VALUES(%s,%s,%s,%s,'postboss',NULL,%s)",
        (
            fight_id,
            run["instance_id"],
            receipt["room_order"],
            player_team,
            receipt["source_order"],
        ),
    )
    from wakfu_server import dungeon_difficulty

    dungeon_difficulty.freeze_encounter(
        db,
        run["instance_id"],
        fight_id,
        expected_selection_revision=expected_selection_revision,
    )
    db.execute(
        "UPDATE dungeon_postboss_nodes SET status='active',active_fight_id=%s "
        "WHERE instance_id=%s AND source_order=%s",
        (fight_id, run["instance_id"], receipt["source_order"]),
    )
    return db.execute(
        "SELECT * FROM dungeon_room_encounters WHERE fight_id=%s", (fight_id,)
    ).fetchone()


def _result(run, receipt, **values):
    return dict(
        instance_id=run["instance_id"],
        current_room=run["current_room"],
        completed=True,
        revision=run["revision"],
        encounter_scope="postboss",
        postboss_source_order=receipt["source_order"],
        postboss_room=receipt["room_order"],
        postboss_revision=receipt["revision"] + 1,
        **values,
    )


def settle(db, run, encounter, fight):
    _completed(run, encounter["instance_id"])
    if not postboss_scope(encounter) or fight.id != encounter["fight_id"]:
        raise ValueError("Invalid postboss encounter scope")
    if (
        fight.phase != "finished"
        or type(fight.winner) is not int
        or fight.winner not in (0, 1)
    ):
        raise ValueError("Postboss settlement lacks an authoritative finished winner")
    status = "victory" if fight.winner == encounter["player_team"] else "defeat"
    if encounter["status"] != "active":
        if encounter["status"] != status or encounter["result"] is None:
            raise ValueError("Conflicting postboss settlement replay")
        return dict(encounter["result"], replay=True)
    receipt = _receipt(db, run["instance_id"], encounter["postboss_source_order"])
    if (
        receipt["catalog_hash"] != run["catalog_hash"]
        or receipt["status"] != "active"
        or receipt["active_fight_id"] != fight.id
        or receipt["room_order"] != encounter["room_order"]
    ):
        raise ValueError("Postboss fight does not own this active node")
    result = _result(run, receipt, victory=status == "victory")
    db.execute(
        "UPDATE dungeon_postboss_nodes SET status=%s,revision=%s,active_fight_id=NULL "
        "WHERE instance_id=%s AND source_order=%s",
        (
            "victory" if result["victory"] else "available",
            result["postboss_revision"],
            run["instance_id"],
            receipt["source_order"],
        ),
    )
    db.execute(
        "UPDATE dungeon_room_encounters SET status=%s,result_revision=%s,result=%s::jsonb WHERE fight_id=%s",
        (status, result["postboss_revision"], json.dumps(result), fight.id),
    )
    return dict(result, replay=False)


def abort(db, run, encounter):
    _completed(run, encounter["instance_id"])
    if not postboss_scope(encounter):
        raise ValueError("Invalid postboss abort scope")
    if encounter["status"] == "aborted" and encounter["result"] is not None:
        return dict(encounter["result"], replay=True)
    receipt = _receipt(db, run["instance_id"], encounter["postboss_source_order"])
    if (
        receipt["catalog_hash"] != run["catalog_hash"]
        or receipt["room_order"] != encounter["room_order"]
        or encounter["status"] != "active"
        or receipt["status"] != "active"
        or receipt["active_fight_id"] != encounter["fight_id"]
    ):
        raise ValueError("Postboss abort lacks its active node")
    result = _result(run, receipt, aborted=True)
    db.execute(
        "UPDATE dungeon_postboss_nodes SET status='available',active_fight_id=NULL,revision=%s "
        "WHERE instance_id=%s AND source_order=%s",
        (result["postboss_revision"], run["instance_id"], receipt["source_order"]),
    )
    db.execute(
        "UPDATE dungeon_room_encounters SET status='aborted',result_revision=%s,result=%s::jsonb WHERE fight_id=%s",
        (result["postboss_revision"], json.dumps(result), encounter["fight_id"]),
    )
    return dict(result, replay=False)


def combat_cells(db, group_key, config, progress, participants):
    receipt = group_receipt(db, group_key)
    if receipt is None:
        return None
    _completed(progress, receipt["instance_id"])
    if receipt["status"] not in ("available", "active"):
        raise ValueError("Postboss node is not available for combat")
    if (
        receipt["catalog_hash"] != progress["catalog_hash"]
        or receipt["catalog_hash"] != config["compiled_plan"]["document_sha256"]
    ):
        raise ValueError("Postboss frozen configuration changed")
    if not any(
        r["order"] == receipt["room_order"]
        and r["source_order"] == receipt["source_order"]
        for r in policy_nodes(config)
    ):
        raise ValueError("Postboss terrain lacks qualified native access")
    rooms = [
        r for r in config["topology"]["rooms"] if r["order"] == receipt["room_order"]
    ]
    cells = frozenset(map(tuple, rooms[0]["cells"])) if len(rooms) == 1 else frozenset()
    if not cells or any(tuple(p) not in cells for p in participants):
        raise ValueError("Postboss combat participant is outside its node terrain")
    return cells


def ensure_groups(db, instance_id, config, groups, *, occupied=()):
    """Transactionally create each qualified node once, without fake main runs."""
    records = policy_nodes(config)
    if not records:
        return ()
    run = db.execute(
        "SELECT * FROM dungeon_room_runs WHERE instance_id=%s FOR UPDATE",
        (instance_id,),
    ).fetchone()
    _completed(run, instance_id)
    if run["catalog_hash"] != config["compiled_plan"]["document_sha256"]:
        raise ValueError("Postboss group configuration differs from the frozen run")
    instance = db.execute(
        "SELECT * FROM dungeon_instances WHERE instance_id=%s", (instance_id,)
    ).fetchone()
    map_id = config["topology"]["asset_map_id"]
    if (
        instance is None
        or instance["status"] != "active"
        or instance["start_map_id"] != map_id
    ):
        raise ValueError("Postboss groups require their active native instance")
    from wakfu_server.dungeon_encounters import roster_members
    from wakfu_server.dungeon_runtime_config import level_selector
    from wakfu_server.combat_terrain import map_geometry
    from wakfu_server.npc_actor_identity import allocate_block

    geometry = map_geometry(map_id)
    published_cells = set(map(tuple, geometry["cells"]))
    db.execute(
        "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
        (f"monster-population:{map_id}:{instance_id}",),
    )
    receipts = []
    for node in records:
        prior = db.execute(
            "SELECT * FROM dungeon_postboss_nodes WHERE instance_id=%s AND source_order=%s FOR UPDATE",
            (instance_id, node["source_order"]),
        ).fetchone()
        if prior is not None:
            if (
                prior["room_order"] != node["order"]
                or prior["catalog_hash"] != run["catalog_hash"]
                or prior["asset_map_id"] != map_id
            ):
                raise ValueError("Conflicting existing postboss node")
            receipts.append(prior)
            continue
        room = next(
            r for r in config["topology"]["rooms"] if r["order"] == node["order"]
        )
        frozen = next(
            r for r in config["compiled_plan"]["rooms"] if r["order"] == node["order"]
        )
        cells = set(map(tuple, room["cells"]))
        if (
            not cells
            or not cells <= published_cells
            or tuple(room["anchor"]) not in cells
        ):
            raise ValueError("Postboss group leaves its published native terrain")
        section = dict(
            geometry,
            cells=tuple(cells),
            edges=tuple(
                (a, b)
                for a, b in geometry["edges"]
                if tuple(a) in cells and tuple(b) in cells
            ),
        )
        roster = [
            dict(
                ref_id=m["ref_id"],
                count=m["count"],
                min_level=m["native_min_level"],
                max_level=m["native_max_level"],
            )
            for m in frozen["monsters"]
        ]
        group_id = db.execute(
            "SELECT nextval('dungeon_room_group_ids') AS id"
        ).fetchone()["id"]
        members = roster_members(
            instance_id,
            roster,
            asset_map_id=map_id,
            anchor=room["anchor"],
            geometry=section,
            group_id=group_id,
            select_level=level_selector(config, room_order=node["order"]),
            actor_id_base=allocate_block(db, 128),
            occupied=occupied,
            player_slots=6,
        )
        groups.register_transaction(db, map_id, instance_id, group_id, members)
        db.execute(
            "INSERT INTO dungeon_postboss_nodes(instance_id,source_order,room_order,asset_map_id,group_id,catalog_hash) VALUES(%s,%s,%s,%s,%s,%s)",
            (
                instance_id,
                node["source_order"],
                node["order"],
                map_id,
                group_id,
                run["catalog_hash"],
            ),
        )
        db.execute(
            "INSERT INTO dungeon_postboss_publication_outbox(instance_id,source_order) VALUES(%s,%s)",
            (instance_id, node["source_order"]),
        )
        receipts.append(_receipt(db, instance_id, node["source_order"]))
    return tuple(receipts)


def publish_pending(store, groups, *, instance_id, publish):
    """Each node publication acknowledges only a successful native send."""
    with groups.lock:
        with store.connection() as db:
            rows = db.execute(
                "SELECT n.*,g.members FROM dungeon_postboss_publication_outbox o "
                "JOIN dungeon_postboss_nodes n USING(instance_id,source_order) "
                "JOIN dungeon_instances i USING(instance_id) JOIN dungeon_room_runs r USING(instance_id) "
                "JOIN combat_groups g ON g.map_id=n.asset_map_id AND g.instance_id=n.instance_id AND g.group_id=n.group_id "
                "WHERE o.instance_id=%s AND NOT o.published AND i.status='active' AND r.status='completed' "
                "AND n.status='available' AND g.status='available' ORDER BY n.source_order",
                (instance_id,),
            ).fetchall()
        from wakfu_server.combat_monster_world import spawn_group

        acknowledged = []
        for row in rows:
            delivered = publish(
                row["asset_map_id"],
                instance_id,
                12608,
                spawn_group(
                    groups._members(
                        dict(members=row["members"], instance_id=instance_id)
                    ),
                    group_id=row["group_id"],
                ),
            )
            if delivered is False:
                continue
            with store.connection() as db:
                db.execute(
                    "UPDATE dungeon_postboss_publication_outbox SET published=true WHERE instance_id=%s AND source_order=%s",
                    (instance_id, row["source_order"]),
                )
            acknowledged.append(row["source_order"])
        return tuple(acknowledged)
