"""Durable dungeon progression; callers share combat settlement transactions."""
import json


def initialize_run(db, instance_id, party_id, plan):
    if not plan.roster_ready:
        raise ValueError("Dungeon roster is not ready")
    instance = db.execute(
        "SELECT party_id,status FROM dungeon_instances WHERE instance_id=%s FOR UPDATE",
        (instance_id,),
    ).fetchone()
    if (
        instance is None
        or instance["party_id"] != party_id
        or instance["status"] != "active"
    ):
        raise ValueError("Dungeon party does not own an active instance")
    rooms = json.dumps(
        [
            dict(
                order=room.order,
                monsters=[
                    dict(
                        ref_id=m.ref_id,
                        count=m.count,
                        min_level=m.native_min_level,
                        max_level=m.native_max_level,
                        role=m.role,
                    )
                    for m in room.monsters
                ],
            )
            for room in plan.rooms
        ]
    )
    db.execute(
        "INSERT INTO dungeon_room_runs(instance_id,party_id,catalog_hash,rooms) "
        "VALUES(%s,%s,%s,%s::jsonb) ON CONFLICT(instance_id) DO NOTHING",
        (instance_id, party_id, plan.document_sha256, rooms),
    )
    row = db.execute(
        "SELECT * FROM dungeon_room_runs WHERE instance_id=%s", (instance_id,)
    ).fetchone()
    if row["catalog_hash"] != plan.document_sha256 or row["party_id"] != party_id:
        raise ValueError("Dungeon run already freezes a different catalog")
    return row


def bind_encounter(db, instance_id, party_id, character_id, fight_id, *, player_team):
    if type(player_team) is not int or player_team not in (0, 1):
        raise ValueError("Invalid player team")
    run = db.execute(
        "SELECT * FROM dungeon_room_runs WHERE instance_id=%s FOR UPDATE",
        (instance_id,),
    ).fetchone()
    if run is None or run["party_id"] != party_id or run["status"] != "active":
        raise ValueError("Dungeon run is not active or owned")
    member = db.execute(
        "SELECT 1 FROM dungeon_instance_members WHERE instance_id=%s "
        "AND party_id=%s AND character_id=%s AND status='active'",
        (instance_id, party_id, character_id),
    ).fetchone()
    participant = db.execute(
        "SELECT team FROM combat_fight_participants WHERE fight_id=%s AND character_id=%s",
        (fight_id, character_id),
    ).fetchone()
    if member is None or participant is None or participant["team"] != player_team:
        raise ValueError("Encounter actor is not an authorized dungeon participant")
    old = db.execute(
        "SELECT * FROM dungeon_room_encounters WHERE fight_id=%s", (fight_id,)
    ).fetchone()
    if old is not None:
        if (
            old["instance_id"] != instance_id
            or old["room_order"] != run["current_room"]
            or old["player_team"] != player_team
        ):
            raise ValueError("Fight is already bound to another encounter")
        return old
    db.execute(
        "INSERT INTO dungeon_room_encounters(fight_id,instance_id,room_order,player_team) VALUES(%s,%s,%s,%s)",
        (fight_id, instance_id, run["current_room"], player_team),
    )
    return db.execute(
        "SELECT * FROM dungeon_room_encounters WHERE fight_id=%s", (fight_id,)
    ).fetchone()


def progression_result(current_room, total_rooms, player_team, winner):
    if type(winner) is not int or winner not in (0, 1):
        raise ValueError("Missing authoritative winner")
    if (
        type(current_room) is not int
        or type(total_rooms) is not int
        or type(player_team) is not int
        or not 1 <= current_room <= total_rooms
        or player_team not in (0, 1)
    ):
        raise ValueError("Invalid dungeon room state")
    victory = winner == player_team
    completed = victory and current_room == total_rooms
    return dict(
        victory=victory,
        completed=completed,
        current_room=current_room + int(victory and not completed),
    )


def settle_encounter(db, fight):
    """Apply an authoritative finished result once, inside reward settlement.

    Normal fights return None. Aborted or unfinished fights cannot advance.
    Transport and next-room spawning happen after this transaction commits.
    """
    encounter = db.execute(
        "SELECT * FROM dungeon_room_encounters WHERE fight_id=%s", (fight.id,)
    ).fetchone()
    if encounter is None:
        return None
    if fight.phase != "finished":
        raise ValueError("Dungeon settlement requires a finished fight")
    run = db.execute(
        "SELECT * FROM dungeon_room_runs WHERE instance_id=%s FOR UPDATE",
        (encounter["instance_id"],),
    ).fetchone()
    encounter = db.execute(
        "SELECT * FROM dungeon_room_encounters WHERE fight_id=%s FOR UPDATE",
        (fight.id,),
    ).fetchone()
    if type(fight.winner) is not int or fight.winner not in (0, 1):
        raise ValueError("Missing authoritative winner")
    expected_status = (
        "victory" if fight.winner == encounter["player_team"] else "defeat"
    )
    if encounter["status"] != "active":
        if encounter["status"] != expected_status:
            raise ValueError("Conflicting replayed dungeon fight result")
        return dict(encounter["result"], replay=True)
    if run["status"] != "active" or run["current_room"] != encounter["room_order"]:
        raise ValueError("Encounter does not belong to the current dungeon room")
    result = progression_result(
        run["current_room"], len(run["rooms"]), encounter["player_team"], fight.winner
    )
    revision = run["revision"] + 1
    db.execute(
        "UPDATE dungeon_room_runs SET current_room=%s,status=%s,revision=%s WHERE instance_id=%s",
        (
            result["current_room"],
            "completed" if result["completed"] else "active",
            revision,
            run["instance_id"],
        ),
    )
    receipt = dict(
        instance_id=run["instance_id"],
        current_room=result["current_room"],
        completed=result["completed"],
        revision=revision,
        victory=result["victory"],
    )
    db.execute(
        "UPDATE dungeon_room_encounters SET status=%s,result_revision=%s,result=%s::jsonb WHERE fight_id=%s",
        (expected_status, revision, json.dumps(receipt), fight.id),
    )
    return dict(receipt, replay=False)
