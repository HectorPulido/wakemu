"""Authoritative native exterior return with durable per-member delivery."""

import struct

from wakfu_server import generic_transports, player_parties


def resolve(character, body, *, entry_map_id, source_allowed):
    if len(body) != 17 or not callable(source_allowed):
        raise ValueError("Invalid dungeon exit request")
    object_id, destination_id, flag, mode = struct.unpack(">qiBi", body)
    if flag != 0 or mode != 2 or character.get("instance_id", 0) <= 0:
        raise ValueError("Invalid dungeon exit mode or instance")
    source = generic_transports.source(character["map_id"], object_id)
    if source is None or source_allowed(character, source) is not True:
        raise ValueError("Dungeon exit source is not authorized")
    destination = next(
        (
            row
            for row in source["destinations"]
            if row["destination_id"] == destination_id
        ),
        None,
    )
    if (
        destination is None
        or destination["map_id"] != entry_map_id
        or destination["criterion"].strip()
        or destination["cyZ"] >= 0
        or destination["cyX"] != 0
        or (destination["cyW"] > 0 and destination["item_reference"] > 0)
        or not destination["native_altitude_walkable"]
    ):
        raise ValueError("Native dungeon exterior return is not supported")
    return dict(destination)


def leave(
    store, account_id, generation, character_id, body, *, source_allowed, in_fight
):
    """Return one member, preserving the other party members' private run.

    Both callbacks must use worker-authoritative state. Exterior packet delivery
    remains durable even when the final departure closes the run.
    """
    return _leave(
        store,
        account_id,
        generation,
        character_id,
        in_fight=in_fight,
        destination_for=lambda db, character, run: resolve(
            character,
            body,
            entry_map_id=run["entry_map_id"],
            source_allowed=source_allowed,
        ),
    )


def automatic_destination(character, run, configuration):
    """Use the pinned run's native exterior approach, never a client target."""
    topology = configuration["topology"]
    from wakfu_server.dungeon_physical_doors import enabled as physical_doors_enabled

    if physical_doors_enabled(topology):
        if character.get("map_id") != topology.get("asset_map_id"):
            raise ValueError("Dungeon exit command belongs to another asset map")
        entrances = [
            item
            for item in topology.get("physical_exit_objects", ())
            if item.get("room_order") == 1
        ]
        if len(entrances) != 1:
            raise ValueError("Dungeon exit command has no unique native exterior route")
        source = generic_transports.source(
            character["map_id"], entrances[0]["source_id"]
        )
        if source is None:
            raise ValueError("Dungeon exit command native source is absent")
        destinations = [
            row
            for row in source["destinations"]
            if row["map_id"] == run["entry_map_id"]
        ]
        if len(destinations) != 1:
            raise ValueError("Dungeon exit command exterior route is ambiguous")
        # Command travel intentionally needs no approach to the entrance object.
        # resolve() still validates native criteria, costs, altitude and instance.
        destination = resolve(
            character,
            struct.pack(">qiBi", source["id"], destinations[0]["destination_id"], 0, 2),
            entry_map_id=run["entry_map_id"],
            source_allowed=lambda actor, candidate: candidate["id"] == source["id"],
        )
        return {key: destination[key] for key in ("map_id", "x", "y", "z")}
    destination = topology.get("completion_destination")
    if (
        topology.get("policy") != "local_accessible_anchor_policy"
        or character["map_id"] != topology.get("asset_map_id")
        or not isinstance(destination, dict)
        or destination.get("provenance", {}).get("policy")
        != "native_entry_approved_walkable_approach"
        or any(
            type(destination.get(key)) is not int for key in ("map_id", "x", "y", "z")
        )
        or destination["map_id"] != run["entry_map_id"]
    ):
        raise ValueError(
            "Dungeon does not have an authorized automatic exterior return"
        )
    return {key: destination[key] for key in ("map_id", "x", "y", "z")}


def leave_automatic(store, account_id, generation, character_id, *, in_fight):
    """Allow a run member to leave local automatic travel outside combat."""
    from wakfu_server import dungeon_runtime

    def destination_for(db, character, run):
        _, configuration = dungeon_runtime.configuration_for_instance(
            db, run["instance_id"]
        )
        return automatic_destination(character, run, configuration)

    return _leave(
        store,
        account_id,
        generation,
        character_id,
        in_fight=in_fight,
        destination_for=destination_for,
    )


def _leave(store, account_id, generation, character_id, *, in_fight, destination_for):
    if not callable(in_fight):
        raise ValueError("Authoritative combat check is required")
    with store.connection() as db:
        # Match entry and party mutation ordering before taking session rows.
        player_parties._lock_members(db, [character_id])
        store.lock_character(db, account_id, generation, character_id)
        character = store.character(account_id, character_id, db=db)
        identity = db.execute(
            "SELECT party_id FROM dungeon_instances WHERE instance_id=%s",
            (character["instance_id"],),
        ).fetchone()
        if identity is None:
            raise ValueError("Character is not in a dungeon run")
        db.execute(
            "SELECT id FROM player_parties WHERE id=%s FOR UPDATE",
            (identity["party_id"],),
        ).fetchone()
        run = db.execute(
            "SELECT * FROM dungeon_instances WHERE instance_id=%s FOR UPDATE",
            (character["instance_id"],),
        ).fetchone()
        member = db.execute(
            "SELECT * FROM dungeon_instance_members WHERE instance_id=%s AND character_id=%s FOR UPDATE",
            (run["instance_id"], character_id),
        ).fetchone()
        if (
            run["status"] not in ("active", "completed")
            or member is None
            or member["status"] != "active"
            or member["session_generation"] != generation
            or in_fight(character_id) is not False
        ):
            raise ValueError("Dungeon member cannot leave in its current state")
        destination = destination_for(db, character, run)
        revision = run["revision"] + 1
        db.execute(
            "UPDATE dungeon_instances SET revision=%s WHERE instance_id=%s",
            (revision, run["instance_id"]),
        )
        db.execute(
            "UPDATE characters SET map_id=%s,instance_id=0,x=%s,y=%s,z=%s WHERE id=%s",
            (
                destination["map_id"],
                destination["x"],
                destination["y"],
                destination["z"],
                character_id,
            ),
        )
        db.execute(
            "UPDATE dungeon_instance_members SET status='returned',ended_at=%s WHERE instance_id=%s AND character_id=%s",
            (store.now(), run["instance_id"], character_id),
        )
        db.execute(
            "UPDATE dungeon_transition_outbox SET status='superseded',superseded_at=%s WHERE character_id=%s AND status='pending'",
            (store.now(), character_id),
        )
        db.execute(
            "INSERT INTO dungeon_transition_outbox(instance_id,party_id,transition_revision,character_id,"
            "session_generation,source_map_id,source_instance_id,source_x,source_y,source_z,"
            "destination_map_id,destination_instance_id,destination_x,destination_y,destination_z,transition_kind) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,0,%s,%s,%s,'exit')",
            (
                run["instance_id"],
                run["party_id"],
                revision,
                character_id,
                generation,
                character["map_id"],
                character["instance_id"],
                character["x"],
                character["y"],
                character["z"],
                destination["map_id"],
                destination["x"],
                destination["y"],
                destination["z"],
            ),
        )
        remaining = db.execute(
            "SELECT 1 FROM dungeon_instance_members WHERE instance_id=%s AND status='active' LIMIT 1",
            (run["instance_id"],),
        ).fetchone()
        if remaining is None:
            db.execute(
                "UPDATE dungeon_instances SET status='closed',ended_at=%s WHERE instance_id=%s",
                (store.now(), run["instance_id"]),
            )
        party_change = player_parties.cleanup_dungeon_solo(db, run["party_id"])
        return dict(
            destination,
            instance_id=0,
            transition_kind="exit",
            party_change=party_change,
        )
