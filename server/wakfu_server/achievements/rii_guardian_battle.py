"""Settlement for a qualified Rii guardian encounter.

The native quest explicitly accepts an attempt. Its original encounter setup
has not been recovered, so a separate producer must record an owned encounter
    receipt before this adapter can ever advance the mission. An arbitrary fight
against the same monster reference is insufficient.
"""


def spawn(store, groups, account_id, generation, character):
    """Create an owned encounter after the captured guardian conversation.

    Original encounter placement and scaling were not captured. A level-six
    native guardian placed adjacent to the player is a local reconstruction.
    """
    import secrets
    from wakfu_server.monsters import owned_instance
    from wakfu_server.npc_actor_identity import allocate_block
    from wakfu_server.combat_terrain import published_geometry
    from wakfu_server.combat_monster_world import spawn_group
    from . import storage

    if (character.get("map_id"), character.get("instance_id")) != (1387, 0):
        return None
    origin = tuple(character[key] for key in ("x", "y", "z"))
    with groups.lock, store.connection() as db:
        db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account_id,))
        store.lock_character(db, account_id, generation, character["id"], selected=True)
        current = store.character(account_id, character["id"], db)
        if tuple(current[k] for k in ("map_id", "instance_id", "x", "y", "z")) != (
            1387,
            0,
            *origin,
        ):
            raise ValueError("Guardian encounter position changed")
        state = storage.load_locked(db, current["id"])
        if (
            5146 not in state["running"]
            or 10583 not in state["objectives"]
            or 10584 in state["objectives"]
        ):
            return None
        active_groups = groups.available(1387, 0)
        active = [
            -member["id"]
            for group in active_groups
            for member in group["members"]
            if member.get("ref") == 5458 and member["id"] < 0
        ]
        owned = (
            db.execute(
                "SELECT 1 FROM character_achievement_events WHERE character_id=%s AND event_key=ANY(%s) LIMIT 1",
                (
                    current["id"],
                    [f"rii-guardian-actor:{identity}" for identity in active],
                ),
            ).fetchone()
            if active
            else None
        )
        if owned:
            # An earlier start may have failed after registration. Select only
            # the owner's actor, never another player's encounter.
            for group in active_groups:
                for member in group["members"]:
                    if member.get("ref") != 5458 or member["id"] >= 0:
                        continue
                    if db.execute(
                        "SELECT 1 FROM character_achievement_events WHERE character_id=%s AND event_key=%s",
                        (current["id"], f"rii-guardian-actor:{-member['id']}"),
                    ).fetchone():
                        return None, dict(member, map_id=1387, instance_id=0)
        occupied = {
            tuple(member[k] for k in ("x", "y", "z"))
            for group in active_groups
            for member in group["members"]
        }
        candidates = [
            cell
            for cell in published_geometry(1387).outgoing.get(origin, ())
            if cell not in occupied
        ]
        if not candidates:
            return None
        actor_id = -allocate_block(db, 1)
        x, y, z = candidates[0]
        monster = owned_instance(
            5458, 6, actor_id, map_id=1387, instance_id=0, x=x, y=y, z=z
        )
        if not storage.record_event(
            db,
            current["id"],
            f"rii-guardian-actor:{-actor_id}",
            {
                "kind": "reconstructed_rii_guardian_actor",
                "owner": current["id"],
                "actor_id": actor_id,
                "ref": 5458,
            },
        ):
            raise ValueError("Guardian actor receipt already exists")
        group_id = secrets.randbits(62) + 1
        groups.register_transaction(db, 1387, 0, group_id, [monster])
    return (12608, spawn_group([monster], group_id=group_id)), monster


def start_request(monster):
    """Build the ordinary server-owned attack request for the spawned guardian."""
    import struct

    if (
        monster.get("ref") != 5458
        or type(monster.get("id")) is not int
        or monster["id"] >= 0
        or monster.get("map_id") != 1387
        or monster.get("instance_id") != 0
    ):
        raise ValueError("Invalid guardian encounter")
    try:
        return struct.pack(
            ">qiihB", monster["id"], monster["x"], monster["y"], monster["z"], 0
        )
    except (KeyError, TypeError, struct.error) as error:
        raise ValueError("Invalid guardian encounter position") from error


def admit(db, owner_id, monsters):
    """Keep an owned guardian encounter from being consumed by someone else."""
    for monster in monsters:
        actor_id = monster.get("id")
        if monster.get("ref") != 5458 or type(actor_id) is not int or actor_id >= 0:
            continue
        rows = db.execute(
            "SELECT character_id,payload FROM character_achievement_events WHERE event_key=%s",
            (f"rii-guardian-actor:{-actor_id}",),
        ).fetchall()
        for row in rows:
            payload = row["payload"]
            if (
                isinstance(payload, dict)
                and payload.get("kind") == "reconstructed_rii_guardian_actor"
                and payload.get("actor_id") == actor_id
                and payload.get("ref") == 5458
                and (
                    row["character_id"] != owner_id or payload.get("owner") != owner_id
                )
            ):
                raise ValueError("This guardian encounter belongs to another player")
    return True


def _retire_lost_encounter(db, target):
    """Retire the owner's single-use guardian after an accredited defeat.

    Group settlement has already released the lease. A lost ordinary fight
    normally leaves its group available, but this reconstructed encounter is
    consumed by either outcome. Delete only its exact single-member group;
    the fight entry already removed its actor from the exploration scene.
    """
    from psycopg.types.json import Jsonb

    db.execute(
        "DELETE FROM combat_groups AS g USING combat_group_members AS m "
        "WHERE g.map_id=1387 AND g.instance_id=0 AND g.status='available' "
        "AND g.generation IS NULL AND g.fight_id IS NULL "
        "AND m.map_id=g.map_id AND m.instance_id=g.instance_id "
        "AND m.group_id=g.group_id AND m.monster_id=%s "
        "AND jsonb_array_length(g.members)=1 AND g.members @> %s",
        (target, Jsonb([{"id": target, "ref": 5458}])),
    )


def settle(db, store, fight, members, monsters):
    """Settle a resolved, owned guardian fight, whether won or lost.

    Called inside the combat settlement transaction. Receipt and participant
    checks precede all changes; this adapter never starts a fight.
    """
    from . import storage

    if (
        fight.phase != "finished"
        or fight.winner not in (0, 1)
        or type(fight.id) is not int
        or fight.id <= 0
    ):
        return {}
    targets = {
        row.get("id")
        for row in monsters
        if row.get("ref") == 5458 and type(row.get("id")) is int and row["id"] < 0
    }
    if len(targets) != 1:
        return {}
    target = targets.pop()
    actors = getattr(fight, "actors", {})
    if target not in actors:
        return {}
    deliveries = {}
    for member in members:
        identity, owner = member.get("character_id"), member.get("account_id")
        if (
            type(identity) is not int
            or identity <= 0
            or type(owner) is not int
            or owner <= 0
            or not member.get("session_generation")
            or member.get("withdrawn", False)
            or identity not in actors
        ):
            continue
        receipt_key = f"rii-guardian-actor:{-target}"
        receipt = db.execute(
            "SELECT payload FROM character_achievement_events "
            "WHERE character_id=%s AND event_key=%s",
            (identity, receipt_key),
        ).fetchone()
        if receipt is None or receipt["payload"] != {
            "kind": "reconstructed_rii_guardian_actor",
            "owner": identity,
            "actor_id": target,
            "ref": 5458,
        }:
            continue
        participant = db.execute(
            "SELECT p.team,f.status,f.fight_kind FROM combat_fight_participants p "
            "JOIN combat_fights f ON f.id=p.fight_id WHERE p.fight_id=%s "
            "AND p.character_id=%s AND p.account_id=%s",
            (fight.id, identity, owner),
        ).fetchone()
        if (
            participant is None
            or participant["status"] != "finished"
            or participant["fight_kind"] != "pve"
            or participant["team"] != actors[identity].team
            or actors[target].team == actors[identity].team
        ):
            continue
        store.lock_character(db, owner, member["session_generation"], identity)
        character = store.character(owner, identity, db)
        before = storage.load_locked(db, identity)
        if (
            5146 not in before["running"]
            or 10582 not in before["objectives"]
            or 10583 not in before["objectives"]
            or 10584 in before["objectives"]
        ):
            continue
        fact = {
            "kind": "reconstructed_rii_guardian_attempt",
            "fight_id": fight.id,
            "actor_id": target,
            "won": actors[identity].team == fight.winner,
        }
        if not storage.record_event(
            db, identity, f"rii-guardian-attempt:{fight.id}", fact
        ):
            continue
        if actors[identity].team != fight.winner:
            _retire_lost_encounter(db, target)
    return deliveries


def pending_cinematic(db, character):
    """Only an owned, settled guardian attempt can launch the ending scene."""
    from . import storage

    if (character.get("map_id"), character.get("instance_id")) != (1387, 0):
        return False
    state = storage.load_locked(db, character["id"])
    if 5146 not in state["running"] or 10584 in state["objectives"]:
        return False
    row = db.execute(
        "SELECT 1 FROM character_achievement_events WHERE character_id=%s "
        "AND event_key LIKE 'rii-guardian-attempt:%%' LIMIT 1",
        (character["id"],),
    ).fetchone()
    return row is not None


def cinematic_packet():
    import struct

    return 13411, struct.pack(">BiiB", 0, 22532, 2548, 0)


def finish_cinematic(store, account_id, generation, source):
    """Commit the observed end-of-scene mission settlement and Rii return."""
    from . import mission_dependencies, mission_progress, rii_departure, storage

    destination = {"map_id": 1385, "instance_id": 0, "x": -19, "y": 25, "z": 5}
    with store.connection() as db:
        store.lock_character(db, account_id, generation, source["id"], selected=True)
        character = store.character(account_id, source["id"], db)
        keys = ("map_id", "instance_id", "x", "y", "z")
        if any(character[k] != source[k] for k in keys) or not pending_cinematic(
            db, character
        ):
            raise ValueError("No guardian ending cinematic is pending")
        before = storage.load_locked(db, character["id"])
        rows = db.execute(
            "SELECT definition_id,data FROM native_quest_metadata_definitions WHERE revision="
            "(SELECT revision FROM native_quest_metadata_releases ORDER BY imported_at DESC LIMIT 1) "
            "AND definition_id=ANY(%s)",
            ([5146, 5160],),
        ).fetchall()
        definitions = {row["definition_id"]: row["data"]["native"] for row in rows}
        if set(definitions) != {5146, 5160}:
            raise ValueError("Missing native Rii guardian quest definitions")
        now_ms = int(store.now().timestamp() * 1000)
        planned = mission_progress.advance_objective(
            before,
            definitions[5146],
            10584,
            character=character,
            store=store,
            now_ms=now_ms,
        )
        if not planned[2]:
            raise ValueError("Guardian completion did not advance")
        planned = rii_departure.activate(
            db, store, character, before, planned, now_ms=now_ms
        )
        result = mission_dependencies.settle(
            db,
            store,
            character,
            before,
            planned,
            definitions,
            ((5160, 10622, 5146),),
            now_ms=now_ms,
        )
        saved = store.transition_map_in_transaction(
            db, account_id, generation, character["id"], character, destination
        )
    return saved, result["packets"]
