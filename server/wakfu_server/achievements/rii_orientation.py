"""Narrow validation for the reconstructed Rii orientation encounter.

The game action producer is responsible for authenticating the fight owner and
the specific encounter target.  A client-provided facing value is never used.
"""


def finish_if_qualified(fight):
    """End the owned lesson after its authenticated rear hit is resolved.

    The original encounter's ending was not captured. This local lesson ends
    as a victory for the owner's team without inventing additional damage or a
    sack death. Quest settlement still consumes the same authoritative hit.
    """
    contract = getattr(fight, "rii_orientation_contract", None)
    if fight.phase != "active" or not isinstance(contract, dict):
        return False
    owner = fight.actors.get(contract.get("owner"))
    target = fight.actors.get(contract.get("target"))
    if owner is None or target is None or owner.hp <= 0 or owner.team == target.team:
        return False
    if not any(
        event.get("kind") == "damage"
        and event.get("rii_orientation_hit") is True
        and event.get("source_id") == owner.id
        and event.get("target_id") == target.id
        for event in fight.events
    ):
        return False
    fight.phase = "finished"
    fight.winner = owner.team
    fight._event("finished", winner=owner.team)
    return True


def damage_is_qualifying(fight, source_id, target_id, amount):
    """Evaluate the live hit only for a server-bound training encounter."""
    contract = getattr(fight, "rii_orientation_contract", None)
    if (
        not isinstance(contract, dict)
        or contract.get("owner") != source_id
        or contract.get("target") != target_id
        or type(amount) is not int
        or amount <= 0
    ):
        return False
    from wakfu_server.combat_ordinary_authority import native_facing

    attacker = fight.actors.get(source_id)
    defender = fight.actors.get(target_id)
    if attacker is None or defender is None:
        return False
    try:
        return native_facing(attacker, defender) == "BACK"
    except ValueError:
        # A missing facing authority must not reject or alter a combat hit.
        return False


def spawn(store, groups, account_id, generation, character):
    """Place one owner-qualified sack near Airyna after accepting her lesson.

    Ref 5466 and the placement are a documented local reconstruction; the
    original encounter descriptor was not recovered.
    """
    import secrets
    from wakfu_server.monsters import owned_instance
    from wakfu_server.npc_actor_identity import allocate_block
    from wakfu_server.combat_terrain import published_geometry
    from wakfu_server.combat_monster_world import spawn_group
    from wakfu_server import npc_world
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
            raise ValueError("Orientation lesson position changed")
        state = storage.load_locked(db, current["id"])
        if 5143 not in state["running"] or 10574 in state["objectives"]:
            return None
        # Sample only after acquiring both the group and owner locks; an
        # earlier snapshot permits concurrent accepts to create two sacks.
        groups_here = groups.available(1388, 0)
        occupied = {
            tuple(m[k] for k in ("x", "y", "z"))
            for group in groups_here
            for m in group["members"]
        }
        npc_cells = [
            tuple(npc[k] for k in ("x", "y", "z"))
            for npc in npc_world.load_scene(db, 1388, 0)
        ]
        occupied.update(npc_cells)
        candidates = [
            cell
            for cell in published_geometry(1388).outgoing.get(origin, ())
            if cell not in occupied
        ]
        if not candidates:
            return None
        active = [
            -m["id"]
            for group in groups_here
            for m in group["members"]
            if m.get("ref") == 5466 and m["id"] < 0
        ]
        if (
            active
            and db.execute(
                "SELECT 1 FROM character_achievement_events WHERE character_id=%s AND event_key=ANY(%s) LIMIT 1",
                (
                    current["id"],
                    [f"rii-orientation-sack:{identity}" for identity in active],
                ),
            ).fetchone()
        ):
            return None
        actor_id = -allocate_block(db, 1)
        # Adjacent tiles can visually overlap NPC sprites, even if their
        # coordinates differ. Prefer the nearest available tile to the player
        # that is furthest from the published NPCs.
        x, y, z = max(
            candidates,
            key=lambda cell: min(
                (abs(cell[0] - npc[0]) + abs(cell[1] - npc[1]) for npc in npc_cells),
                default=0,
            ),
        )
        monster = owned_instance(
            5466, 1, actor_id, map_id=1388, instance_id=0, x=x, y=y, z=z
        )
        storage.record_event(
            db,
            current["id"],
            f"rii-orientation-sack:{-actor_id}",
            {
                "kind": "reconstructed_rii_orientation_sack",
                "owner": current["id"],
                "actor_id": actor_id,
                "ref": 5466,
            },
        )
        group_id = secrets.randbits(62) + 1
        groups.register_transaction(db, 1388, 0, group_id, [monster])
    return (12608, spawn_group([monster], group_id=group_id))


def owned_target(db, owner_id, monsters):
    """Return the actor backed by this character's exact orientation receipt."""
    for monster in monsters:
        actor_id = monster.get("id")
        if monster.get("ref") != 5466 or type(actor_id) is not int or actor_id >= 0:
            continue
        row = db.execute(
            "SELECT payload FROM character_achievement_events WHERE character_id=%s AND event_key=%s",
            (owner_id, f"rii-orientation-sack:{-actor_id}"),
        ).fetchone()
        if row and row["payload"] == {
            "kind": "reconstructed_rii_orientation_sack",
            "owner": owner_id,
            "actor_id": actor_id,
            "ref": 5466,
        }:
            return actor_id
    return None


def bind(db, fight, owner_id, monsters):
    """Bind only a sack created for this owner; do not alter other fights."""
    actor_id = owned_target(db, owner_id, monsters)
    if actor_id is None:
        return False
    fight.rii_orientation_contract = {"owner": owner_id, "target": actor_id}
    return True


def admit(db, owner_id, monsters):
    """Prevent another player from taking a character's lesson encounter."""
    for monster in monsters:
        actor_id = monster.get("id")
        if monster.get("ref") != 5466 or type(actor_id) is not int or actor_id >= 0:
            continue
        rows = db.execute(
            "SELECT character_id,payload FROM character_achievement_events WHERE event_key=%s",
            (f"rii-orientation-sack:{-actor_id}",),
        ).fetchall()
        for row in rows:
            payload = row["payload"]
            if (
                isinstance(payload, dict)
                and payload.get("kind") == "reconstructed_rii_orientation_sack"
                and payload.get("actor_id") == actor_id
                and payload.get("ref") == 5466
            ):
                if row["character_id"] != owner_id or payload.get("owner") != owner_id:
                    raise ValueError(
                        "This training encounter belongs to another player"
                    )
    return True


def settle_participants(db, store, fight, members, monsters):
    """Settle a verified owned lesson in the fight's final transaction."""
    contract = getattr(fight, "rii_orientation_contract", None)
    if (
        fight.phase != "finished"
        or fight.winner not in (0, 1)
        or not isinstance(contract, dict)
        or type(fight.id) is not int
        or fight.id <= 0
    ):
        return {}
    owner_id, target_id = contract.get("owner"), contract.get("target")
    if (
        type(owner_id) is not int
        or owner_id <= 0
        or type(target_id) is not int
        or target_id >= 0
        or not any(m.get("id") == target_id and m.get("ref") == 5466 for m in monsters)
    ):
        return {}
    actors = getattr(fight, "actors", {})
    if (
        owner_id not in actors
        or target_id not in actors
        or actors[owner_id].team == actors[target_id].team
        or fight.winner != actors[owner_id].team
    ):
        return {}
    member = next((m for m in members if m.get("character_id") == owner_id), None)
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
        (owner_id, f"rii-orientation-sack:{-target_id}"),
    ).fetchone()
    if receipt is None or receipt["payload"] != {
        "kind": "reconstructed_rii_orientation_sack",
        "owner": owner_id,
        "actor_id": target_id,
        "ref": 5466,
    }:
        return {}
    participant = db.execute(
        "SELECT p.team,f.status,f.fight_kind FROM combat_fight_participants p "
        "JOIN combat_fights f ON f.id=p.fight_id WHERE p.fight_id=%s "
        "AND p.character_id=%s AND p.account_id=%s",
        (fight.id, owner_id, member["account_id"]),
    ).fetchone()
    if (
        participant is None
        or participant["status"] != "finished"
        or participant["fight_kind"] != "pve"
        or participant["team"] != actors[owner_id].team
    ):
        return {}
    store.lock_character(
        db, member["account_id"], member["session_generation"], owner_id
    )
    character = store.character(member["account_id"], owner_id, db)
    packets = settle(db, store, character, fight, fight.events)
    return {member["account_id"]: packets} if packets else {}


def settle(db, store, character, fight, events):
    """Record the authenticated rear hit as the first objective exactly once."""
    from . import mission_progress, storage, wire
    from .service import _owner

    contract = getattr(fight, "rii_orientation_contract", None)
    if (
        not isinstance(contract, dict)
        or contract.get("owner") != character["id"]
        or not any(
            event.get("kind") == "damage"
            and event.get("rii_orientation_hit") is True
            and event.get("source_id") == character["id"]
            and event.get("target_id") == contract.get("target")
            for event in events
        )
    ):
        return []
    _owner(db, character)
    before = storage.load_locked(db, character["id"])
    if 5143 not in before["running"] or 10574 in before["objectives"]:
        return []
    row = db.execute(
        "SELECT data FROM native_quest_metadata_definitions WHERE revision="
        "(SELECT revision FROM native_quest_metadata_releases ORDER BY imported_at DESC LIMIT 1) "
        "AND definition_id=%s",
        (5143,),
    ).fetchone()
    if row is None:
        raise ValueError("Missing orientation quest definition")
    now_ms = int(store.now().timestamp() * 1000)
    after, intents, objectives, completed = mission_progress.advance_objective(
        before,
        row["data"]["native"],
        10574,
        character=character,
        store=store,
        now_ms=now_ms,
    )
    if intents or completed:
        raise ValueError("Unexpected orientation quest completion")
    if not storage.record_event(
        db,
        character["id"],
        "rii-orientation-objective:10574",
        {
            "kind": "reconstructed_rii_orientation_hit",
            "fight_id": fight.id,
            "target_id": contract["target"],
        },
    ):
        raise ValueError("Orientation receipt exists without progress")
    hidden_row = db.execute(
        "SELECT data FROM native_quest_metadata_definitions WHERE revision="
        "(SELECT revision FROM native_quest_metadata_releases ORDER BY imported_at DESC LIMIT 1) "
        "AND definition_id=%s",
        (5154,),
    ).fetchone()
    if hidden_row is None:
        raise ValueError("Missing orientation introduction flag")
    hidden = hidden_row["data"]["native"]
    flag = [item for item in hidden.get("cjJ", []) if item.get("d") == 10606]
    if (
        hidden.get("d") != 5154
        or hidden.get("native_class") != "aJM"
        or hidden.get("aqb") is not True
        or hidden.get("isVisible") is not False
        or len(flag) != 1
        or flag[0].get("ckc") != ""
        or flag[0].get("cke") != ""
        or flag[0].get("ckf") != []
    ):
        raise ValueError("Orientation introduction flag differs from native definition")
    if 10606 not in after["objectives"]:
        if not storage.record_event(
            db,
            character["id"],
            "rii-introduction-flag:10606",
            {"kind": "reconstructed_rii_introduction", "objective_id": 10606},
        ):
            raise ValueError("Orientation flag receipt exists without progress")
        after["objectives"] = sorted(set(after["objectives"]) | {10606})
        objectives = list(objectives) + [10606]
    storage.store(db, character["id"], after)
    return wire.changes(
        character["id"],
        before,
        after,
        objectives,
        completed,
        now_ms,
        definitions={5143: row["data"]["native"], 5154: hidden},
    )
