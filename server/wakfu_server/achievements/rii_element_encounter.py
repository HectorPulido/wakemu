"""Owned world encounter for Airyna's reconstructed elemental lesson.

The sack reference and adjacent placement are local reconstructions. No
client-provided actor or target can create or claim this contract.
"""

REF = 5466
KEY = "rii-element-sack:"
KIND = "reconstructed_rii_element_sack"


def _payload(owner, actor_id):
    return {"kind": KIND, "owner": owner, "actor_id": actor_id, "ref": REF}


def spawn(store, groups, account_id, generation, character, *, repeat=False):
    """Create at most one available owned sack when the lesson is eligible."""
    import secrets
    from wakfu_server.monsters import owned_instance
    from wakfu_server.npc_actor_identity import allocate_block
    from wakfu_server.combat_terrain import published_geometry
    from wakfu_server.combat_monster_world import spawn_group
    from . import storage

    if (character.get("map_id"), character.get("instance_id")) != (1388, 0):
        return None
    origin = tuple(character[k] for k in ("x", "y", "z"))
    with groups.lock, store.connection() as db:
        db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account_id,))
        store.lock_character(db, account_id, generation, character["id"], selected=True)
        current = store.character(account_id, character["id"], db)
        if tuple(current[k] for k in ("map_id", "instance_id", "x", "y", "z")) != (
            1388,
            0,
            *origin,
        ):
            raise ValueError("Elemental lesson position changed")
        state = storage.load_locked(db, current["id"])
        if (
            5143 not in state["running"]
            or 10574 not in state["objectives"]
            or (10575 in state["objectives"] and not repeat)
        ):
            return None
        groups_here = groups.available(1388, 0)
        # Count only the sacks this owner created: the dojo can hold other
        # players' training encounters and reusing one strands the auto-start.
        active = []
        for group in groups_here:
            for member in group["members"]:
                identity = member.get("id")
                if (
                    member.get("ref") != REF
                    or type(identity) is not int
                    or identity >= 0
                ):
                    continue
                if db.execute(
                    "SELECT 1 FROM character_achievement_events WHERE character_id=%s AND event_key=%s",
                    (current["id"], KEY + str(-identity)),
                ).fetchone():
                    active.append(-identity)
        if active and not repeat:
            return None
        occupied = {
            tuple(m[k] for k in ("x", "y", "z"))
            for group in groups_here
            for m in group["members"]
        }
        cells = [
            cell
            for cell in published_geometry(1388).outgoing.get(origin, ())
            if cell not in occupied
        ]
        if not cells:
            return None
        actor_id = -allocate_block(db, 1)
        x, y, z = cells[0]
        monster = owned_instance(
            REF, 1, actor_id, map_id=1388, instance_id=0, x=x, y=y, z=z
        )
        if not storage.record_event(
            db, current["id"], KEY + str(-actor_id), _payload(current["id"], actor_id)
        ):
            raise ValueError("Duplicate elemental lesson encounter receipt")
        group_id = secrets.randbits(62) + 1
        groups.register_transaction(db, 1388, 0, group_id, [monster])
    return 12608, spawn_group([monster], group_id=group_id)


def admit(db, owner_id, monsters):
    """Reject another character's owned elemental sack before fight entry."""
    for monster in monsters:
        actor_id = monster.get("id")
        if monster.get("ref") != REF or type(actor_id) is not int or actor_id >= 0:
            continue
        rows = db.execute(
            "SELECT character_id,payload FROM character_achievement_events WHERE event_key=%s",
            (KEY + str(-actor_id),),
        ).fetchall()
        for row in rows:
            if (
                row["payload"] == _payload(row["character_id"], actor_id)
                and row["character_id"] != owner_id
            ):
                raise ValueError("This training encounter belongs to another player")
    return True


def bind(db, fight, owner_id, monsters):
    """Bind an owner-receipted sack to this single fight snapshot."""
    for monster in monsters:
        actor_id = monster.get("id")
        if monster.get("ref") != REF or type(actor_id) is not int or actor_id >= 0:
            continue
        row = db.execute(
            "SELECT payload FROM character_achievement_events WHERE character_id=%s AND event_key=%s",
            (owner_id, KEY + str(-actor_id)),
        ).fetchone()
        if row and row["payload"] == _payload(owner_id, actor_id):
            fight.rii_element_lesson_contract = {
                "owner": owner_id,
                "target": actor_id,
                "hits": 0,
                "last_turn": None,
            }
            return True
    return False


def settle_participants(db, store, fight, members, monsters):
    """Settle four qualified turns in the same transaction as fight closure."""
    contract = getattr(fight, "rii_element_lesson_contract", None)
    if (
        fight.phase != "finished"
        or fight.winner not in (0, 1)
        or not isinstance(contract, dict)
        or contract.get("hits") != 4
        or type(fight.id) is not int
        or fight.id <= 0
    ):
        return {}
    owner, target = contract.get("owner"), contract.get("target")
    if (
        type(owner) is not int
        or owner <= 0
        or type(target) is not int
        or target >= 0
        or not any(m.get("id") == target and m.get("ref") == REF for m in monsters)
    ):
        return {}
    actors = fight.actors
    if (
        owner not in actors
        or target not in actors
        or actors[owner].team == actors[target].team
        or fight.winner != actors[owner].team
    ):
        return {}
    if contract.get("native_lesson") is True and actors[target].hp > 0:
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
    receipt = db.execute(
        "SELECT payload FROM character_achievement_events WHERE character_id=%s AND event_key=%s",
        (owner, KEY + str(-target)),
    ).fetchone()
    if not receipt or receipt["payload"] != _payload(owner, target):
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
    if 5143 not in before["running"] or 10575 in before["objectives"]:
        return {}
    row = db.execute(
        "SELECT data FROM native_quest_metadata_definitions WHERE revision="
        "(SELECT revision FROM native_quest_metadata_releases ORDER BY imported_at DESC LIMIT 1) "
        "AND definition_id=%s",
        (5143,),
    ).fetchone()
    if row is None:
        raise ValueError("Missing elemental lesson quest definition")
    now_ms = int(store.now().timestamp() * 1000)
    after, intents, objectives, completed = mission_progress.advance_objective(
        before,
        row["data"]["native"],
        10575,
        character=character,
        store=store,
        now_ms=now_ms,
    )
    if intents or completed:
        raise ValueError("Unexpected elemental lesson quest completion")
    if not storage.record_event(
        db,
        owner,
        "rii-element-objective:10575",
        {
            "kind": "reconstructed_rii_element_lesson",
            "fight_id": fight.id,
            "target_id": target,
            "hits": 4,
        },
    ):
        raise ValueError("Elemental lesson receipt exists without progress")
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
