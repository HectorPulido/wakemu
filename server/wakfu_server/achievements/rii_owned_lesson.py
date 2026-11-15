"""Server-owned tutorial encounter primitives shared by Rii lessons.

These helpers create and bind owner-specific world actors against durable
receipts. They do not grant spells or authorize client-supplied objectives.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Lesson:
    key: str
    kind: str
    reference: int
    objective: int
    prerequisite: int

    def __post_init__(self):
        if (
            not self.key
            or not self.kind
            or any(
                type(x) is not int or x <= 0
                for x in (self.reference, self.objective, self.prerequisite)
            )
        ):
            raise ValueError("Invalid owned tutorial lesson")


DISTANCE = Lesson(
    "rii-distance-sack:", "reconstructed_rii_distance_sack", 5466, 10576, 10575
)
MOVEMENT = Lesson(
    "rii-movement-sack:", "reconstructed_rii_movement_sack", 5466, 10610, 10609
)
STATES = Lesson("rii-states-sack:", "reconstructed_rii_states_sack", 5466, 10611, 10610)


def payload(lesson, owner, actor_id):
    if (
        type(owner) is not int
        or owner <= 0
        or type(actor_id) is not int
        or actor_id >= 0
    ):
        raise ValueError("Invalid owned tutorial actor")
    return {
        "kind": lesson.kind,
        "owner": owner,
        "actor_id": actor_id,
        "ref": lesson.reference,
    }


def spawn(store, groups, account_id, generation, character, lesson, *, repeat=False):
    """Create at most one available owned actor for an eligible lesson.

    Placement and actor reference are explicitly reconstructed and must be
    validated per lesson before the caller exposes an entry point. A durable
    player receipt and group are written in the same owned transaction.
    """
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
            raise ValueError("Tutorial lesson position changed")
        state = storage.load_locked(db, current["id"])
        if (
            5143 not in state["running"]
            or lesson.prerequisite not in state["objectives"]
            or (lesson.objective in state["objectives"] and not repeat)
        ):
            return None
        groups_here = groups.available(1388, 0)
        for group in groups_here:
            members = group["members"]
            if len(members) != 1 or bind(db, lesson, current["id"], members) is None:
                continue
            # A defeat or abandonment makes the same owned group available
            # again. Floor lessons must keep the player beside that group;
            # returning None would make stage() send them back upstairs.
            if character.get("_rii_training_objective") == lesson.objective:
                from .rii_training_arena import mark_setup_ready_in_transaction

                mark_setup_ready_in_transaction(db, character, lesson.objective)
                return 12608, spawn_group(members, group_id=group["key"][2])
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
        actor = -allocate_block(db, 1)
        x, y, z = cells[0]
        monster = owned_instance(
            lesson.reference, 1, actor, map_id=1388, instance_id=0, x=x, y=y, z=z
        )
        if not storage.record_event(
            db,
            current["id"],
            lesson.key + str(-actor),
            payload(lesson, current["id"], actor),
        ):
            raise ValueError("Duplicate tutorial encounter receipt")
        group_id = secrets.randbits(62) + 1
        groups.register_transaction(db, 1388, 0, group_id, [monster])
        scene = 12608, spawn_group([monster], group_id=group_id)
        if lesson.objective in (10608, 10610, 10611):
            from .rii_training_arena import mark_setup_ready_in_transaction

            mark_setup_ready_in_transaction(db, character, lesson.objective)
    return scene


def admit(db, lesson, owner, monsters):
    """Protect only actors bearing an exact lesson receipt from other owners."""
    for monster in monsters:
        actor = monster.get("id")
        if (
            monster.get("ref") != lesson.reference
            or type(actor) is not int
            or actor >= 0
        ):
            continue
        rows = db.execute(
            "SELECT character_id,payload FROM character_achievement_events WHERE event_key=%s",
            (lesson.key + str(-actor),),
        ).fetchall()
        for row in rows:
            if (
                row["payload"] == payload(lesson, row["character_id"], actor)
                and row["character_id"] != owner
            ):
                raise ValueError("This training encounter belongs to another player")
    return True


def bind(db, lesson, owner, monsters):
    """Return an initial contract only for the owner's exact lesson receipt."""
    for monster in monsters:
        actor = monster.get("id")
        if (
            monster.get("ref") != lesson.reference
            or type(actor) is not int
            or actor >= 0
        ):
            continue
        row = db.execute(
            "SELECT payload FROM character_achievement_events WHERE character_id=%s AND event_key=%s",
            (owner, lesson.key + str(-actor)),
        ).fetchone()
        if row and row["payload"] == payload(lesson, owner, actor):
            return {"owner": owner, "target": actor, "hits": 0}
    return None


def settle_participants(db, store, lesson, fight, members, monsters, *, contract_name):
    """Settle a qualified four-hit lesson inside its fight-finish transaction.

    A caller must provide the server-owned fight and original combat roster;
    a client cannot specify a player, actor, objective, or hit counter here.
    """
    contract = getattr(fight, contract_name, None)
    native_los = (
        contract_name == "rii_los_lesson_contract"
        and isinstance(contract, dict)
        and contract.get("native_los_areas") is True
    )
    if (
        fight.phase != "finished"
        or fight.winner not in (0, 1)
        or not isinstance(contract, dict)
        or (not native_los and contract.get("hits") != 4)
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
        or not any(
            m.get("id") == target and m.get("ref") == lesson.reference for m in monsters
        )
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
    if (native_los or contract.get("native_lesson") is True) and actors[target].hp > 0:
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
    row = db.execute(
        "SELECT payload FROM character_achievement_events WHERE character_id=%s AND event_key=%s",
        (owner, lesson.key + str(-target)),
    ).fetchone()
    if not row or row["payload"] != payload(lesson, owner, target):
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
    if 5143 not in before["running"] or lesson.objective in before["objectives"]:
        return {}
    definition = db.execute(
        "SELECT data FROM native_quest_metadata_definitions WHERE revision="
        "(SELECT revision FROM native_quest_metadata_releases ORDER BY imported_at DESC LIMIT 1) "
        "AND definition_id=%s",
        (5143,),
    ).fetchone()
    if definition is None:
        raise ValueError("Missing native tutorial quest definition")
    now_ms = int(store.now().timestamp() * 1000)
    planned = mission_progress.advance_objective(
        before,
        definition["data"]["native"],
        lesson.objective,
        character=character,
        store=store,
        now_ms=now_ms,
    )
    after, intents, objectives, completed = planned
    if not storage.record_event(
        db,
        owner,
        "rii-lesson-objective:" + str(lesson.objective),
        {
            "kind": "reconstructed_rii_lesson",
            "fight_id": fight.id,
            "target_id": target,
            "hits": contract.get("hits", 0) if native_los else 4,
        },
    ):
        raise ValueError("Tutorial completion receipt exists without progress")
    if completed:
        # A final lesson can complete the child quest and, in turn, its
        # parent. Reserve and deliver both sets of native rewards in the same
        # fight transaction rather than rejecting the final objective.
        from . import mission_dependencies

        parent = db.execute(
            "SELECT data FROM native_quest_metadata_definitions WHERE revision="
            "(SELECT revision FROM native_quest_metadata_releases ORDER BY imported_at DESC LIMIT 1) "
            "AND definition_id=%s",
            (5160,),
        ).fetchone()
        if parent is None:
            raise ValueError("Missing native tutorial parent quest definition")
        result = mission_dependencies.settle(
            db,
            store,
            character,
            before,
            planned,
            {5143: definition["data"]["native"], 5160: parent["data"]["native"]},
            ((5160, 10616, 5143),),
            now_ms=now_ms,
        )
        return {member["account_id"]: result["packets"]} if result["packets"] else {}
    if intents:
        raise ValueError("Incomplete tutorial quest cannot grant rewards")
    storage.store(db, owner, after)
    packets = wire.changes(
        owner,
        before,
        after,
        objectives,
        completed,
        now_ms,
        definitions={5143: definition["data"]["native"]},
    )
    return {member["account_id"]: packets} if packets else {}
