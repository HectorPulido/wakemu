"""Authoritative native exterior return with durable per-member delivery."""

import struct

from wakfu_server import generic_transports, player_parties


def validate_foreign_exterior(topology):
    """Validate each explicitly pinned foreign exit against complete native data."""
    policy = topology.get("native_foreign_exterior_policy")
    if policy is None:
        return {}
    if (
        topology.get("policy") != "native_mixed_victory_policy"
        or not isinstance(policy, dict)
        or set(policy) != {"reason", "bindings"}
        or not isinstance(policy["reason"], str)
        or not policy["reason"].strip()
        or not isinstance(policy["bindings"], list)
        or not policy["bindings"]
    ):
        raise ValueError(
            "Foreign native exits require explicit reviewed mixed bindings"
        )
    from wakfu_server.dungeon_runtime_config import canonical_hash
    from wakfu_server.combat_geometry import published_geometry

    reviewed = {
        row["source_id"]: row for row in topology.get("physical_exit_objects", ())
    }
    result = {}
    for binding in policy["bindings"]:
        if (
            not isinstance(binding, dict)
            or set(binding)
            != {"source_id", "source_sha256", "destination_id", "destination"}
            or type(binding["source_id"]) is not int
            or type(binding["destination_id"]) is not int
            or binding["source_id"] in result
            or binding["source_id"] not in reviewed
        ):
            raise ValueError("Foreign native exit identity is invalid or duplicated")
        identity = binding["source_id"]
        source = generic_transports.source(topology["asset_map_id"], identity)
        target = binding["destination"]
        if (
            not isinstance(target, dict)
            or set(target) != {"map_id", "x", "y", "z"}
            or any(type(value) is not int for value in target.values())
            or source is None
            or canonical_hash(source) != binding["source_sha256"]
        ):
            raise ValueError("Foreign native exit source hash or destination changed")
        destinations = [
            row
            for row in source["destinations"]
            if row["destination_id"] == binding["destination_id"]
        ]
        frozen = reviewed[identity]
        if (
            len(destinations) != 1
            or frozen.get("destination_id") != binding["destination_id"]
            or frozen.get("destination") != target
        ):
            raise ValueError(
                "Foreign native exit contradicts its pinned exterior binding"
            )
        native = destinations[0]
        if (
            any(native[key] != target[key] for key in target)
            or native["criterion"].strip()
            or native["cyZ"] >= 0
            or native["cyX"] != 0
            or native["cyW"] > 0
            and native["item_reference"] > 0
            or native["native_altitude_walkable"] is not True
            or tuple(target[key] for key in ("x", "y", "z"))
            not in published_geometry(target["map_id"]).cells
        ):
            raise ValueError(
                "Foreign native exit is not an exact free walkable endpoint"
            )
        result[identity] = binding
    return result


def resolve(character, body, *, entry_map_id, source_allowed, topology=None):
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
    foreign = {}
    if destination is not None and destination["map_id"] != entry_map_id:
        if topology is None or topology.get("asset_map_id") != character["map_id"]:
            raise ValueError("Foreign native exit has no pinned current-map contract")
        foreign = validate_foreign_exterior(topology).get(object_id, {})
    if (
        destination is None
        or destination["map_id"] != entry_map_id
        and (
            foreign.get("destination_id") != destination_id
            or foreign.get("destination")
            != {key: destination[key] for key in ("map_id", "x", "y", "z")}
        )
        or destination["criterion"].strip()
        or destination["cyZ"] >= 0
        or destination["cyX"] != 0
        or (destination["cyW"] > 0 and destination["item_reference"] > 0)
        or not destination["native_altitude_walkable"]
    ):
        raise ValueError("Native dungeon exterior return is not supported")
    return dict(destination)


def leave(
    store,
    account_id,
    generation,
    character_id,
    body,
    *,
    source_allowed,
    in_fight,
    positions=None,
):
    """Return one member, preserving the other party members' private run.

    Both callbacks must use worker-authoritative state. Exterior packet delivery
    remains durable even when the final departure closes the run.
    """

    def destination_for(db, character, run):
        from wakfu_server import dungeon_runtime

        topology = None
        pinned_config = db.execute(
            "SELECT 1 FROM dungeon_runtime_configurations WHERE route_key=%s AND policy_version=%s",
            (run["context_route_key"], run["context_policy_version"]),
        ).fetchone()
        if pinned_config is not None:
            _, configuration = dungeon_runtime.configuration_for_instance(
                db, run["instance_id"]
            )
            topology = configuration["topology"]
        if (
            topology is not None
            and topology.get("policy") == "native_shared_arena_sequential_policy"
        ):
            progress = db.execute(
                "SELECT status FROM dungeon_room_runs WHERE instance_id=%s",
                (run["instance_id"],),
            ).fetchone()
            if progress is None or progress["status"] != "completed":
                raise ValueError(
                    "Shared arena exit is locked until the final encounter"
                )
            identity = struct.unpack(">q", body[:8])[0] if len(body) == 17 else None
            if not any(
                row["source_id"] == identity
                for row in topology.get("physical_exit_objects", ())
            ):
                raise ValueError("Shared arena exit is not a reviewed native binding")
        if len(body) == 17:
            identity, target, _, _ = struct.unpack(">qiBi", body)
            source = generic_transports.source(character["map_id"], identity)
            if source is not None and any(
                row["destination_id"] == target and row["map_id"] != run["entry_map_id"]
                for row in source["destinations"]
            ):
                _, configuration = dungeon_runtime.configuration_for_instance(
                    db, run["instance_id"]
                )
                topology = configuration["topology"]
                binding = next(
                    (
                        row
                        for row in topology.get("physical_exit_objects", ())
                        if row["source_id"] == identity
                    ),
                    None,
                )
                progress = db.execute(
                    "SELECT status FROM dungeon_room_runs WHERE instance_id=%s",
                    (run["instance_id"],),
                ).fetchone()
                if binding is None or (
                    binding["room_order"] != 1
                    and (progress is None or progress["status"] != "completed")
                ):
                    raise ValueError("Foreign native dungeon exit is locked")
        return resolve(
            character,
            body,
            entry_map_id=run["entry_map_id"],
            source_allowed=source_allowed,
            topology=topology,
        )

    return _leave(
        store,
        account_id,
        generation,
        character_id,
        in_fight=in_fight,
        destination_for=destination_for,
        positions=positions,
    )


def automatic_destination(character, run, configuration):
    """Use the pinned run's native exterior approach, never a client target."""
    topology = configuration["topology"]
    from wakfu_server.dungeon_native_flow import enabled as native_flow_enabled

    if native_flow_enabled(topology):
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
        foreign = validate_foreign_exterior(topology).get(source["id"])
        destinations = [
            row
            for row in source["destinations"]
            if row["map_id"] == run["entry_map_id"]
            or foreign is not None
            and row["destination_id"] == foreign["destination_id"]
            and {key: row[key] for key in ("map_id", "x", "y", "z")}
            == foreign["destination"]
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
            topology=topology,
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


def leave_automatic(
    store, account_id, generation, character_id, *, in_fight, positions=None
):
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
        positions=positions,
    )


def _leave(
    store,
    account_id,
    generation,
    character_id,
    *,
    in_fight,
    destination_for,
    positions=None,
):
    if not callable(in_fight):
        raise ValueError("Authoritative combat check is required")
    if positions is not None:
        from .dungeon_position_barrier import run_account_exit

        return run_account_exit(
            store,
            positions,
            account_id,
            transition=lambda: _leave(
                store,
                account_id,
                generation,
                character_id,
                in_fight=in_fight,
                destination_for=destination_for,
            ),
        )
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
        owned_heroes = db.execute(
            "SELECT h.character_id FROM account_hero_slots h JOIN account_hero_rosters r USING(account_id) "
            "JOIN dungeon_instance_members m ON m.character_id=h.character_id "
            "WHERE h.account_id=%s AND r.leader_id=%s AND m.instance_id=%s AND m.status='active'",
            (account_id, character_id, run["instance_id"]),
        ).fetchall()
        for owned in owned_heroes:
            hero_id = owned["character_id"]
            store.lock_character(db, account_id, generation, hero_id, selected=False)
            if in_fight(hero_id) is not False:
                raise ValueError("Owned hero cannot leave during combat")
            db.execute(
                "UPDATE characters SET map_id=%s,instance_id=0,x=%s,y=%s,z=%s WHERE id=%s",
                tuple(destination[key] for key in ("map_id", "x", "y", "z"))
                + (hero_id,),
            )
            db.execute(
                "UPDATE dungeon_instance_members SET status='returned',ended_at=%s "
                "WHERE instance_id=%s AND character_id=%s",
                (store.now(), run["instance_id"], hero_id),
            )
            db.execute(
                "UPDATE dungeon_transition_outbox SET status='superseded',superseded_at=%s "
                "WHERE character_id=%s AND status='pending'",
                (store.now(), hero_id),
            )
        from wakfu_server.characters.dungeon_modulation_health import reconcile

        reconcile(
            store,
            db,
            [character_id, *(owned["character_id"] for owned in owned_heroes)],
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
