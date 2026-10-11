"""Return the complete owned party after a committed final dungeon victory.

Call after every fight participant has returned to exploration. Existing durable
transition delivery owns network hydration; this module sends no client packets.
"""
from psycopg.types.json import Jsonb
from wakfu_server import player_parties


def completion_destination(result, topology):
    """Allow local automatic exterior return only for a final victory."""
    if topology.get("policy") != "local_accessible_anchor_policy":
        return None
    if result.get("victory") is not True or result.get("completed") is not True:
        raise ValueError("Automatic exit requires committed final victory")
    destination = topology.get("completion_destination")
    if (
        not isinstance(destination, dict)
        or destination.get("provenance", {}).get("policy")
        != "native_entry_approved_walkable_approach"
    ):
        raise ValueError("Automatic exterior destination lacks native provenance")
    if any(type(destination.get(key)) is not int for key in ("map_id", "x", "y", "z")):
        raise ValueError(
            "Automatic exterior destination must be integral native terrain"
        )
    return {key: destination[key] for key in ("map_id", "x", "y", "z")}


def complete(store, instance_id, fight_id, *, topology, in_fight):
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
        destination = completion_destination(result, topology)
        if destination is None:
            return None
        if destination["map_id"] != run["entry_map_id"]:
            raise ValueError("Automatic exit does not match the owned native entry map")
        if result.get("auto_exit_revision") is not None:
            return dict(
                destination,
                instance_id=0,
                revision=result["auto_exit_revision"],
                members=tuple(member_ids),
                replay=True,
            )
        if (
            run["status"] not in ("active", "completed")
            or progress is None
            or progress["status"] != "completed"
            or progress["party_id"] != run["party_id"]
            or progress["current_room"] != len(progress["rooms"])
            or progress["current_room"] != result["current_room"]
            or encounter["room_order"] != result["current_room"]
            or progress["revision"] != result["revision"]
        ):
            raise ValueError("Dungeon victory no longer owns the completed run")
        if not member_ids or [member["id"] for member in members] != member_ids:
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
        revision = run["revision"] + 1
        db.execute(
            "UPDATE dungeon_instances SET revision=%s,status='closed',ended_at=%s WHERE instance_id=%s",
            (revision, now, instance_id),
        )
        for member in members:
            db.execute(
                "UPDATE characters SET map_id=%s,instance_id=0,x=%s,y=%s,z=%s WHERE id=%s",
                (
                    destination["map_id"],
                    destination["x"],
                    destination["y"],
                    destination["z"],
                    member["id"],
                ),
            )
            db.execute(
                "UPDATE dungeon_instance_members SET status='returned',ended_at=%s WHERE instance_id=%s AND character_id=%s",
                (now, instance_id, member["id"]),
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
                "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'exit')",
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
                    0,
                    destination["x"],
                    destination["y"],
                    destination["z"],
                ),
            )
        from wakfu_server.characters.dungeon_modulation_health import reconcile

        reconcile(store, db, member_ids)
        party_change = player_parties.cleanup_dungeon_solo(db, run["party_id"])
        saved = dict(result, auto_exit_revision=revision)
        db.execute(
            "UPDATE dungeon_room_encounters SET result=%s WHERE fight_id=%s",
            (Jsonb(saved), fight_id),
        )
        return dict(
            destination,
            instance_id=0,
            revision=revision,
            members=tuple(member_ids),
            replay=False,
            party_change=party_change,
        )
