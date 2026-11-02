"""Native private-room travel gated by a committed victory receipt."""

import struct

from wakfu_server import generic_transports, player_parties
from wakfu_server import dungeon_achievement_authority


def resolve(
    character,
    body,
    *,
    source_allowed,
    room_for_position,
    criterion_allowed,
    topology=None,
):
    """Resolve a native door using a server-owned topology mapper.

    ``room_for_position(map_id,x,y,z)`` must derive the room from verified native
    topology, never from client-supplied room numbers or teleporter ID ordering.
    """
    if len(body) != 17 or not all(
        callable(check)
        for check in (source_allowed, room_for_position, criterion_allowed)
    ):
        raise ValueError("Authoritative dungeon door checks are required")
    object_id, destination_id, flag, mode = struct.unpack(">qiBi", body)
    if flag != 0 or mode != 2 or character.get("instance_id", 0) <= 0:
        raise ValueError("Invalid dungeon door request")
    source = generic_transports.source(character["map_id"], object_id)
    if topology is not None:
        from wakfu_server import dungeon_native_flow

        if object_id in dungeon_native_flow.disabled_source_ids(
            topology, generic_transports._CATALOG
        ):
            raise ValueError(
                "Native source is explicitly excluded by the local dungeon policy"
            )
    if source is None or source_allowed(character, source) is not True:
        raise ValueError("Dungeon door source is not authorized")
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
        or destination["map_id"] != character["map_id"]
        or destination["cyZ"] >= 0
        or destination["cyX"] != 0
        or (destination["cyW"] > 0 and destination["item_reference"] > 0)
        or not destination["native_altitude_walkable"]
        or (
            destination["criterion"].strip()
            and criterion_allowed(destination["criterion"]) is not True
        )
    ):
        raise ValueError("Unsupported native dungeon door destination")
    source_room = room_for_position(
        source["map_id"], source["x"], source["y"], source["z"]
    )
    destination_room = room_for_position(
        destination["map_id"], destination["x"], destination["y"], destination["z"]
    )
    mixed_binding = None
    if topology is not None and topology.get("policy") == "native_mixed_victory_policy":
        from wakfu_server import dungeon_native_flow

        matches = [
            b
            for b in topology["doors"]
            if b["source_id"] == object_id and b["destination_id"] == destination_id
        ]
        if len(matches) != 1:
            raise ValueError("Native mixed transport has no unique reviewed binding")
        mixed_binding = matches[0]
        source_room = dungeon_native_flow.object_room(topology, source)
        if (
            source_room != mixed_binding["source_room"]
            or destination_room != mixed_binding["destination_room"]
            or tuple(destination[k] for k in ("x", "y", "z"))
            != tuple(mixed_binding["destination_position"])
        ):
            raise ValueError("Native mixed transport contradicts reviewed endpoints")
        dungeon_native_flow.validate_transport_binding(topology, mixed_binding)
    if (
        type(source_room) is not int
        or type(destination_room) is not int
        or min(source_room, destination_room) <= 0
        or (abs(destination_room - source_room) != 1 and mixed_binding is None)
    ):
        raise ValueError("Dungeon door topology does not identify reviewed rooms")
    if topology is not None and not (
        mixed_binding is not None
        and mixed_binding.get("binding_kind") == "native_entry_transfer"
    ):
        from wakfu_server.dungeon_optional_rooms import require_main_room

        require_main_room(topology, destination_room)
    return source_room, destination_room, dict(destination)


def _advance(
    store,
    account_id,
    generation,
    character_id,
    body,
    *,
    source_allowed,
    room_for_position,
    in_fight,
    topology=None,
    on_arrival=None,
    allowed_position_accounts=None,
):
    """Move the active party atomically within its authorized room frontier.

    Forward travel requires the destination's preceding committed victory.
    Reviewed mixed-policy hub and intra-stage travel preserve progress and
    use the same durable outbox.
    """
    if not callable(in_fight):
        raise ValueError("Authoritative combat check is required")
    if on_arrival is not None and not callable(on_arrival):
        raise ValueError("Authoritative arrival callback is required")
    entry_paths = topology is not None and topology.get("entry_path_policy") is not None
    from wakfu_server.dungeon_entry_paths import (
        lock_members_nowait,
        owner_lock_query,
        lock_accounts_nowait,
    )

    with store.connection() as db:
        initial = db.execute(
            "SELECT instance_id,party_id FROM dungeon_instance_members "
            "WHERE character_id=%s AND status='active'",
            (character_id,),
        ).fetchone()
        if initial is None:
            raise ValueError("Character has no active dungeon membership")
        member_ids = [
            row["character_id"]
            for row in db.execute(
                "SELECT character_id FROM dungeon_instance_members WHERE instance_id=%s "
                "AND status='active' ORDER BY character_id",
                (initial["instance_id"],),
            ).fetchall()
        ]
        if topology is not None and topology.get("entry_path_policy") is not None:
            # This entry point may hold the position account barrier. Never
            # wait for a run/instance holder that may be waiting for accounts.
            db.execute(
                "SELECT instance_id FROM dungeon_instances WHERE instance_id=%s FOR UPDATE NOWAIT",
                (initial["instance_id"],),
            ).fetchone()
            db.execute(
                "SELECT instance_id FROM dungeon_room_runs WHERE instance_id=%s FOR UPDATE NOWAIT",
                (initial["instance_id"],),
            ).fetchone()
        if entry_paths:
            lock_members_nowait(db, member_ids)
        else:
            player_parties._lock_members(db, member_ids)
        if entry_paths:
            accounts = db.execute(
                "SELECT DISTINCT account_id FROM characters WHERE id=ANY(%s)",
                (member_ids,),
            ).fetchall()
            lock_accounts_nowait(db, [row["account_id"] for row in accounts])
        members = owner_lock_query(
            db,
            "SELECT c.id,c.account_id,c.map_id,c.instance_id,c.x,c.y,c.z,"
            "s.generation,s.character_id AS selected_character_id,s.expires_at,"
            "m.session_generation AS membership_generation "
            "FROM dungeon_instance_members m JOIN characters c ON c.id=m.character_id "
            "JOIN sessions s ON s.account_id=c.account_id "
            "WHERE m.instance_id=%s AND m.status='active' AND c.deleted_at IS NULL "
            "ORDER BY c.id FOR UPDATE OF s,c",
            (initial["instance_id"],),
            nonblocking=entry_paths,
        ).fetchall()
        owner_lock_query(
            db,
            "SELECT id FROM player_parties WHERE id=%s FOR UPDATE",
            (initial["party_id"],),
            nonblocking=entry_paths,
        ).fetchone()
        run = db.execute(
            "SELECT * FROM dungeon_instances WHERE instance_id=%s FOR UPDATE",
            (initial["instance_id"],),
        ).fetchone()
        progress = db.execute(
            "SELECT * FROM dungeon_room_runs WHERE instance_id=%s FOR UPDATE",
            (initial["instance_id"],),
        ).fetchone()
        if (
            run is None
            or run["status"] != "active"
            or progress is None
            or progress["status"] not in ("active", "completed")
        ):
            raise ValueError("Dungeon run cannot advance through a door")
        if [member["id"] for member in members] != member_ids:
            raise ValueError("Dungeon roster changed during door travel")
        if allowed_position_accounts is not None and any(
            member["account_id"] not in allowed_position_accounts for member in members
        ):
            raise ValueError("Dungeon door party changed outside position barrier")
        actor = next(
            (member for member in members if member["id"] == character_id), None
        )
        if (
            actor is None
            or actor["account_id"] != account_id
            or actor["generation"] != generation
        ):
            raise ValueError("Dungeon door session is stale")
        from wakfu_server import heroes

        for member in members:
            if (
                not heroes.session_authorized(db, member)
                or member["expires_at"] <= store.now()
                or member["membership_generation"] != member["generation"]
                or member["instance_id"] != run["instance_id"]
                or member["map_id"] != actor["map_id"]
                or in_fight(member["id"]) is not False
            ):
                raise ValueError(
                    "Every active dungeon member must be online outside combat"
                )
        if topology is not None and topology.get("entry_path_policy") is not None:
            from wakfu_server import dungeon_runtime

            _, fresh_config = dungeon_runtime.configuration_for_instance(
                db, run["instance_id"]
            )
            if fresh_config["topology"].get("entry_path_source_sha256") != topology.get(
                "entry_path_source_sha256"
            ):
                raise ValueError("Pinned native entrance path changed")
            topology = fresh_config["topology"]
        if topology is not None and topology.get("optional_vote_access") is not None:
            from wakfu_server import dungeon_runtime

            _, fresh_config = dungeon_runtime.configuration_for_instance(
                db, run["instance_id"]
            )
            if (
                fresh_config["topology"].get("optional_vote_access")
                != topology["optional_vote_access"]
            ):
                raise ValueError("Pinned optional transport changed")
            topology = fresh_config["topology"]
        from wakfu_server.dungeon_optional_vote_geometry import resolve_transport

        side_destination = (
            None
            if topology is None
            else resolve_transport(
                topology,
                actor,
                body,
                source_allowed=source_allowed,
            )
        )
        if side_destination is not None:
            destination = side_destination
        else:
            source_room, destination_room, destination = resolve(
                actor,
                body,
                source_allowed=source_allowed,
                room_for_position=room_for_position,
                criterion_allowed=lambda criterion: dungeon_achievement_authority.evaluate(
                    store,
                    criterion,
                    character=store.character(account_id, character_id, db),
                ),
                topology=topology,
            )
            entry_transfer = None
            if topology is not None and topology.get("entry_path_policy") is not None:
                from wakfu_server import dungeon_entry_paths

                source_id, destination_id = struct.unpack_from(">qi", body)
                matches = [
                    record
                    for record in topology["entry_path_policy"]["entry_transfers"]
                    if record["source_id"] == source_id
                    and record["destination_id"] == destination_id
                ]
                if matches:
                    entry_transfer = dungeon_entry_paths.transfer_binding(
                        topology, source_id, destination_id
                    )
                    if str(progress.get("branch_key") or "").startswith(
                        dungeon_entry_paths.HINT_PREFIX
                    ):
                        if on_arrival is None:
                            raise ValueError(
                                "Native entrance choice requires atomic group hydration"
                            )
                        from wakfu_server import dungeon_runtime_config

                        source_config = dungeon_runtime_config.pinned_configuration(
                            db, run["context_route_key"], run["context_policy_version"]
                        )
                        dungeon_entry_paths.select_unfought_path(
                            db, run, source_config, entry_transfer["to_path"]
                        )
            if (
                entry_transfer is None
                and max(source_room, destination_room) > progress["current_room"]
            ):
                raise ValueError(
                    "Dungeon next room has no committed victory authorization"
                )
            if entry_transfer is None and destination_room > source_room:
                receipt = db.execute(
                    "SELECT result FROM dungeon_room_encounters WHERE instance_id=%s "
                    "AND room_order=%s AND status='victory' ORDER BY result_revision DESC LIMIT 1",
                    (run["instance_id"], destination_room - 1),
                ).fetchone()
                if (
                    receipt is None
                    or receipt["result"].get("victory") is not True
                    or receipt["result"].get("current_room") != destination_room
                ):
                    raise ValueError(
                        "Dungeon next room has no committed victory authorization"
                    )
            if topology is not None and topology.get("branch_routes"):
                from wakfu_server import dungeon_branches

                if on_arrival is None:
                    raise ValueError(
                        "Native branch travel requires atomic encounter initialization"
                    )
                dungeon_branches.select(
                    db, run["instance_id"], topology, struct.unpack_from(">q", body)[0]
                )
        revision = run["revision"] + 1
        db.execute(
            "UPDATE dungeon_instances SET revision=%s WHERE instance_id=%s",
            (revision, run["instance_id"]),
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
                (store.now(), member["id"]),
            )
            if member["selected_character_id"] != member["id"]:
                continue
            db.execute(
                "INSERT INTO dungeon_transition_outbox(instance_id,party_id,transition_revision,character_id,"
                "session_generation,source_map_id,source_instance_id,source_x,source_y,source_z,"
                "destination_map_id,destination_instance_id,destination_x,destination_y,destination_z,transition_kind) "
                "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'door')",
                (
                    run["instance_id"],
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
                    run["instance_id"],
                    destination["x"],
                    destination["y"],
                    destination["z"],
                ),
            )
        if on_arrival is not None:
            on_arrival(db, run["instance_id"])
        return dict(
            destination,
            instance_id=run["instance_id"],
            transition_kind="door",
            members=tuple(member_ids),
        )


def advance(
    store,
    account_id,
    generation,
    character_id,
    body,
    *,
    source_allowed,
    room_for_position,
    in_fight,
    topology=None,
    on_arrival=None,
    positions=None,
):
    """Travel through a door with the complete instance's positions fenced."""

    from psycopg.errors import LockNotAvailable

    def transition(allowed_accounts=None):
        try:
            return _advance(
                store,
                account_id,
                generation,
                character_id,
                body,
                source_allowed=source_allowed,
                room_for_position=room_for_position,
                in_fight=in_fight,
                topology=topology,
                on_arrival=on_arrival,
                allowed_position_accounts=allowed_accounts,
            )
        except LockNotAvailable as error:
            # The transaction context has already rolled back. The position
            # barrier remains authoritative and the normal action rejection
            # keeps the client connected to retry the same native interaction.
            raise ValueError(
                "Dungeon native travel is busy; retry interaction"
            ) from error

    if positions is None:
        return transition()
    from .dungeon_position_barrier import run_manual_transition

    return run_manual_transition(
        store,
        positions,
        account_id,
        character_id,
        transition=transition,
    )
