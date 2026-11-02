"""Move the complete owned party after a committed room victory and return.

Call after every fight participant has returned to exploration. Existing durable
transition delivery owns network hydration; this module sends no client packets.
"""
from psycopg.types.json import Jsonb
from wakfu_server import player_parties
from .dungeon_transition_recovery import RecoverableDungeonDestination


def next_anchor(result, topology):
    """Authorize only the next room of a non-final victory receipt."""
    if result.get("victory") is not True:
        raise ValueError("Automatic dungeon travel requires a victory receipt")
    if result.get("completed") is True:
        return None
    order = result.get("current_room")
    rooms = [room for room in topology["rooms"] if room["order"] == order]
    if type(order) is not int or order <= 1 or len(rooms) != 1:
        raise RecoverableDungeonDestination(
            "destination_room",
            "Automatic dungeon destination is not a verified next room",
        )
    local_policy = topology.get("policy") == "local_accessible_anchor_policy"
    if local_policy:
        if topology.get("doors"):
            raise ValueError("Local room policy cannot claim native doors")
        if tuple(rooms[0]["anchor"]) not in {tuple(cell) for cell in rooms[0]["cells"]}:
            raise RecoverableDungeonDestination(
                "room_anchor_outside_cells",
                "Local room anchor is not in its native accessible cells",
            )
        links = topology.get("auto_edges", ())
    else:
        if topology.get("auto_edges"):
            raise ValueError("Automatic room edges require an explicit local policy")
        links = topology["doors"]
    doors = [
        door
        for door in links
        if door["source_room"] == order - 1 and door["destination_room"] == order
    ]
    if len(doors) != 1:
        raise RecoverableDungeonDestination(
            "forward_link_ambiguous",
            "Automatic dungeon travel lacks a unique authorized forward link",
        )
    if tuple(doors[0]["anchor"]) != tuple(rooms[0]["anchor"]):
        raise RecoverableDungeonDestination(
            "forward_anchor_mismatch",
            "Automatic dungeon travel lacks a unique authorized forward link",
        )
    return dict(
        map_id=topology["asset_map_id"],
        **dict(zip(("x", "y", "z"), rooms[0]["anchor"]))
    )


def advance(store, instance_id, fight_id, *, topology, in_fight):
    """Atomically relocate all active run members, exactly once per victory.

    A participant still in combat causes a deferred result, never a partial
    party move. Caller invokes this after combat return has committed for all.
    """
    if not callable(in_fight):
        raise ValueError("Authoritative combat check is required")
    with store.connection() as db:
        member_ids = [
            row["character_id"]
            for row in db.execute(
                "SELECT character_id FROM dungeon_instance_members WHERE instance_id=%s "
                "AND status='active' ORDER BY character_id",
                (instance_id,),
            ).fetchall()
        ]
        if not member_ids:
            raise ValueError("Dungeon has no active owned members")
        player_parties._lock_members(db, member_ids)
        members = db.execute(
            "SELECT c.id,c.account_id,c.map_id,c.instance_id,c.x,c.y,c.z,"
            "s.generation,s.character_id AS selected_character_id,s.expires_at,"
            "m.session_generation AS membership_generation "
            "FROM dungeon_instance_members m JOIN characters c ON c.id=m.character_id "
            "JOIN sessions s ON s.account_id=c.account_id "
            "WHERE m.instance_id=%s AND m.status='active' AND c.deleted_at IS NULL "
            "ORDER BY c.id FOR UPDATE OF s,c",
            (instance_id,),
        ).fetchall()
        initial = db.execute(
            "SELECT party_id FROM dungeon_instances WHERE instance_id=%s",
            (instance_id,),
        ).fetchone()
        if initial is None:
            raise ValueError("Unknown dungeon instance")
        db.execute(
            "SELECT id FROM player_parties WHERE id=%s FOR UPDATE",
            (initial["party_id"],),
        ).fetchone()
        run = db.execute(
            "SELECT * FROM dungeon_instances WHERE instance_id=%s FOR UPDATE",
            (instance_id,),
        ).fetchone()
        progress = db.execute(
            "SELECT * FROM dungeon_room_runs WHERE instance_id=%s FOR UPDATE",
            (instance_id,),
        ).fetchone()
        encounter = db.execute(
            "SELECT * FROM dungeon_room_encounters WHERE fight_id=%s FOR UPDATE",
            (fight_id,),
        ).fetchone()
        if (
            encounter is None
            or encounter["instance_id"] != instance_id
            or encounter["status"] != "victory"
        ):
            raise ValueError("Missing committed dungeon victory")
        result = encounter["result"]
        from . import dungeon_transition_recovery as recovery

        recovery_journal = None
        destination_error = None
        try:
            destination = next_anchor(result, topology)
        except RecoverableDungeonDestination as error:
            destination = None
            destination_error = error
        if destination is None and destination_error is None:
            return None
        if result.get("auto_transition_revision") is not None:
            if destination_error is not None:
                repaired = recovery.forward_anchor(result, topology, destination_error)
                if repaired is None:
                    return dict(
                        deferred=True,
                        reason="recovery_replay_unverified",
                        instance_id=instance_id,
                    )
                destination, _ = repaired
            return dict(
                destination,
                instance_id=instance_id,
                revision=result["auto_transition_revision"],
                members=tuple(member_ids),
                replay=True,
            )
        if (
            run["status"] != "active"
            or progress is None
            or progress["status"] != "active"
            or progress["party_id"] != run["party_id"]
            or progress["current_room"] != result["current_room"]
            or encounter["room_order"] + 1 != result["current_room"]
            or progress["revision"] != result["revision"]
        ):
            raise ValueError("Dungeon victory no longer owns the next room")
        if [member["id"] for member in members] != member_ids:
            return dict(
                deferred=True, reason="member_unavailable", instance_id=instance_id
            )
        from wakfu_server.characters.heroes import session_authorized

        now = store.now()
        for member in members:
            if (
                not session_authorized(db, member)
                or member["expires_at"] <= now
                or member["membership_generation"] != member["generation"]
                or member["instance_id"] != instance_id
                or member["map_id"] != topology["asset_map_id"]
                or in_fight(member["id"]) is not False
            ):
                return dict(
                    deferred=True, reason="members_not_ready", instance_id=instance_id
                )
        if destination_error is not None:
            now = store.now()
            if not recovery.retry_due(result, topology, now):
                return dict(
                    deferred=True,
                    reason="recovery_backoff",
                    instance_id=instance_id,
                    recovery_waiting=True,
                    code=destination_error.code,
                    fight_id=fight_id,
                    attempts=result.get("transition_recovery", {}).get("attempts", 0),
                )
            repaired = recovery.forward_anchor(result, topology, destination_error)
            if repaired is None:
                journal = recovery.failure_journal(
                    result, topology, destination_error, now
                )
                db.execute(
                    "UPDATE dungeon_room_encounters SET result=%s WHERE fight_id=%s",
                    (Jsonb(dict(result, transition_recovery=journal)), fight_id),
                )
                return dict(
                    recovery_required=True,
                    code=destination_error.code,
                    instance_id=instance_id,
                    fight_id=fight_id,
                    exit_authorized=recovery.exit_authorized(
                        topology, run["entry_map_id"]
                    ),
                    attempts=journal["attempts"],
                )
            destination, recovery_journal = repaired
        revision = run["revision"] + 1
        db.execute(
            "UPDATE dungeon_instances SET revision=%s WHERE instance_id=%s",
            (revision, instance_id),
        )
        for member in members:
            db.execute(
                "UPDATE characters SET map_id=%s,x=%s,y=%s,z=%s WHERE id=%s",
                (
                    destination["map_id"],
                    destination["x"],
                    destination["y"],
                    destination["z"],
                    member["id"],
                ),
            )
            db.execute(
                "UPDATE dungeon_transition_outbox SET status='superseded',superseded_at=%s "
                "WHERE character_id=%s AND status='pending'",
                (now, member["id"]),
            )
            if member["selected_character_id"] != member["id"]:
                continue
            db.execute(
                "INSERT INTO dungeon_transition_outbox(instance_id,party_id,transition_revision,character_id,"
                "session_generation,source_map_id,source_instance_id,source_x,source_y,source_z,"
                "destination_map_id,destination_instance_id,destination_x,destination_y,destination_z,transition_kind) "
                "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'door')",
                (
                    instance_id,
                    run["party_id"],
                    revision,
                    member["id"],
                    member["generation"],
                    member["map_id"],
                    member["instance_id"],
                    member["x"],
                    member["y"],
                    member["z"],
                    destination["map_id"],
                    instance_id,
                    destination["x"],
                    destination["y"],
                    destination["z"],
                ),
            )
        saved = dict(result, auto_transition_revision=revision)
        if recovery_journal is not None:
            saved["transition_recovery"] = dict(
                recovery_journal,
                attempts=1,
                repaired_at=recovery.journal_timestamp(now),
            )
        db.execute(
            "UPDATE dungeon_room_encounters SET result=%s WHERE fight_id=%s",
            (Jsonb(saved), fight_id),
        )
        return dict(
            destination,
            instance_id=instance_id,
            revision=revision,
            members=tuple(member_ids),
            replay=False,
            recovery=recovery_journal,
        )
