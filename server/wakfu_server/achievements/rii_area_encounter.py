"""Owned four-sack encounter primitives for the Rii area lesson.

The installed client supplies the four-sack objective and native spell areas;
the sack breed, layout, and encounter creation below are reconstructions.  No
dialogue or combat handler invokes this module until the multi-target producer,
movement packets and complete settlement are separately integrated.
"""

from .lesson_area import SACK_COUNT, formation

REF = 5466
KEY = "rii-area-sack:"
KIND = "reconstructed_rii_area_sack"


def payload(owner, actor):
    if type(owner) is not int or owner <= 0 or type(actor) is not int or actor >= 0:
        raise ValueError("Invalid area lesson ownership")
    return {"kind": KIND, "owner": owner, "actor_id": actor, "ref": REF}


def spawn(store, groups, account_id, generation, character, *, repeat=False):
    """Atomically publish one complete owner-receipted group when eligible.

    `repeat` reruns a finished exercise through Airyna's native "already done"
    entry, so the completed objective must not block a new own group.
    """
    import secrets
    from wakfu_server.combat_monster_world import spawn_group
    from wakfu_server.combat_terrain import published_geometry
    from wakfu_server.monsters import owned_instance
    from wakfu_server.npc_actor_identity import allocate_block
    from wakfu_server.rii_lesson_spell_catalog import catalog
    from . import storage

    if (character.get("map_id"), character.get("instance_id")) != (1388, 0):
        return None
    origin = tuple(character[key] for key in ("x", "y", "z"))
    with groups.lock, store.connection() as db:
        db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account_id,))
        store.lock_character(db, account_id, generation, character["id"], selected=True)
        current = store.character(account_id, character["id"], db)
        if tuple(current[key] for key in ("map_id", "instance_id", "x", "y", "z")) != (
            1388,
            0,
            *origin,
        ):
            raise ValueError("Area lesson position changed")
        state = storage.load_locked(db, current["id"])
        if (
            5143 not in state["running"]
            or 10608 not in state["objectives"]
            or (10609 in state["objectives"] and not repeat)
        ):
            return None
        groups_here = groups.available(1388, 0)
        for group in groups_here:
            members = group["members"]
            if bind(db, current["id"], members) is None:
                continue
            # Preserve the existing four-sack encounter after a failed fight.
            # The transit and group readiness must commit together as on spawn.
            from .rii_training_arena import mark_setup_ready_in_transaction

            mark_setup_ready_in_transaction(db, character, 10609)
            return 12608, spawn_group(members, group_id=group["key"][2])
        occupied = {
            tuple(m[key] for key in ("x", "y", "z"))
            for group in groups_here
            for m in group["members"]
        }
        geometry = published_geometry(1388)
        layout = formation(
            geometry.outgoing.keys(),
            occupied,
            anchor=origin,
            phase=0,
            effects=catalog()["effects"],
        )
        if layout is None:
            return None
        _, cells = layout
        base = allocate_block(db, SACK_COUNT)
        monsters = []
        for index, (x, y, z) in enumerate(cells):
            actor = -(base + index)
            monster = owned_instance(
                REF, 1, actor, map_id=1388, instance_id=0, x=x, y=y, z=z
            )
            if not storage.record_event(
                db, current["id"], KEY + str(-actor), payload(current["id"], actor)
            ):
                raise ValueError("Duplicate area lesson encounter receipt")
            monsters.append(monster)
        group_id = secrets.randbits(62) + 1
        groups.register_transaction(db, 1388, 0, group_id, monsters)
        scene = 12608, spawn_group(monsters, group_id=group_id)
        from .rii_training_arena import mark_setup_ready_in_transaction

        mark_setup_ready_in_transaction(db, character, 10609)
    return scene


def admit(db, owner, monsters):
    """Protect only sacks identified by exact durable lesson receipts."""
    for monster in monsters:
        actor = monster.get("id")
        if monster.get("ref") != REF or type(actor) is not int or actor >= 0:
            continue
        rows = db.execute(
            "SELECT character_id,payload FROM character_achievement_events WHERE event_key=%s",
            (KEY + str(-actor),),
        ).fetchall()
        for row in rows:
            if (
                row["payload"] == payload(row["character_id"], actor)
                and row["character_id"] != owner
            ):
                raise ValueError("This training encounter belongs to another player")
    return True


def bind(db, owner, monsters):
    """Bind exactly four owned original sacks to a fight contract."""
    candidates = [
        m
        for m in monsters
        if m.get("ref") == REF and type(m.get("id")) is int and m["id"] < 0
    ]
    if (
        len(candidates) != SACK_COUNT
        or len({m["id"] for m in candidates}) != SACK_COUNT
    ):
        return None
    for monster in candidates:
        actor = monster["id"]
        row = db.execute(
            "SELECT payload FROM character_achievement_events WHERE character_id=%s AND event_key=%s",
            (owner, KEY + str(-actor)),
        ).fetchone()
        if row is None or row["payload"] != payload(owner, actor):
            return None
    return {
        "owner": owner,
        "targets": sorted(m["id"] for m in candidates),
        "hits": 0,
        "actions": [],
    }


def settle_participants(db, store, fight, members, monsters):
    """Settle all four qualified area casts in the fight's transaction."""
    contract = getattr(fight, "rii_area_lesson_contract", None)
    if (
        fight.phase != "finished"
        or fight.winner not in (0, 1)
        or not isinstance(contract, dict)
        or contract.get("hits") != 4
        or type(fight.id) is not int
        or fight.id <= 0
    ):
        return {}
    owner, targets = contract.get("owner"), contract.get("targets")
    if (
        type(owner) is not int
        or owner <= 0
        or not isinstance(targets, list)
        or len(targets) != SACK_COUNT
        or len(set(targets)) != SACK_COUNT
        or any(type(target) is not int or target >= 0 for target in targets)
    ):
        return {}
    actors = fight.actors
    original = {m.get("id") for m in monsters if m.get("ref") == REF}
    if (
        owner not in actors
        or not set(targets) <= original
        or any(
            target not in actors or actors[target].team == actors[owner].team
            for target in targets
        )
        or fight.winner != actors[owner].team
    ):
        return {}
    if contract.get("native_lesson") is True and any(
        actors[target].hp > 0 for target in targets
    ):
        return {}
    member = next((m for m in members if m.get("character_id") == owner), None)
    if (
        member is None
        or type(member.get("account_id")) is not int
        or member["account_id"] <= 0
        or not member.get("session_generation")
        or member.get("withdrawn", False)
    ):
        return {}
    bound = bind(db, owner, monsters)
    if bound is None or set(bound["targets"]) != set(targets):
        return {}
    participant = db.execute(
        "SELECT p.team,f.status,f.fight_kind FROM combat_fight_participants p "
        "JOIN combat_fights f ON f.id=p.fight_id WHERE p.fight_id=%s "
        "AND p.character_id=%s AND p.account_id=%s",
        (fight.id, owner, member["account_id"]),
    ).fetchone()
    if (
        participant is None
        or participant["status"] != "finished"
        or participant["fight_kind"] != "pve"
        or participant["team"] != actors[owner].team
    ):
        return {}
    store.lock_character(db, member["account_id"], member["session_generation"], owner)
    character = store.character(member["account_id"], owner, db)
    from . import mission_progress, storage, wire

    before = storage.load_locked(db, owner)
    if 5143 not in before["running"] or 10609 in before["objectives"]:
        return {}
    row = db.execute(
        "SELECT data FROM native_quest_metadata_definitions WHERE revision="
        "(SELECT revision FROM native_quest_metadata_releases ORDER BY imported_at DESC LIMIT 1) "
        "AND definition_id=%s",
        (5143,),
    ).fetchone()
    if row is None:
        raise ValueError("Missing native tutorial quest definition")
    now_ms = int(store.now().timestamp() * 1000)
    after, intents, objectives, completed = mission_progress.advance_objective(
        before,
        row["data"]["native"],
        10609,
        character=character,
        store=store,
        now_ms=now_ms,
    )
    if intents or completed:
        raise ValueError("Unexpected area lesson quest completion")
    if not storage.record_event(
        db,
        owner,
        "rii-lesson-objective:10609",
        {
            "kind": "reconstructed_rii_area_lesson",
            "fight_id": fight.id,
            "target_ids": targets,
            "hits": 4,
        },
    ):
        raise ValueError("Area lesson receipt exists without progress")
    storage.store(db, owner, after)
    packets = wire.changes(
        owner,
        before,
        after,
        objectives,
        completed,
        now_ms,
        definitions={5143: row["data"]["native"]},
    )
    return {member["account_id"]: packets} if packets else {}
