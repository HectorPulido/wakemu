"""Native private-room travel gated by a committed victory receipt."""

import struct

from wakfu_server import generic_transports, player_parties
from wakfu_server import dungeon_criteria


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
        player_parties._lock_members(db, member_ids)
        members = db.execute(
            "SELECT c.id,c.account_id,c.map_id,c.instance_id,c.x,c.y,c.z,"
            "s.generation,s.character_id AS selected_character_id,s.expires_at,"
            "m.session_generation AS membership_generation "
            "FROM dungeon_instance_members m JOIN characters c ON c.id=m.character_id "
            "JOIN sessions s ON s.account_id=c.account_id "
            "WHERE m.instance_id=%s AND m.status='active' AND c.deleted_at IS NULL "
            "ORDER BY c.id FOR UPDATE OF s,c",
            (initial["instance_id"],),
        ).fetchall()
        db.execute(
            "SELECT id FROM player_parties WHERE id=%s FOR UPDATE",
            (initial["party_id"],),
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
        for member in members:
            if (
                member["selected_character_id"] != member["id"]
                or member["expires_at"] <= store.now()
                or member["membership_generation"] != member["generation"]
                or member["instance_id"] != run["instance_id"]
                or member["map_id"] != actor["map_id"]
                or in_fight(member["id"]) is not False
            ):
                raise ValueError(
                    "Every active dungeon member must be online outside combat"
                )
        source_room, destination_room, destination = resolve(
            actor,
            body,
            source_allowed=source_allowed,
            room_for_position=room_for_position,
            criterion_allowed=lambda criterion: dungeon_criteria.evaluate(
                store, criterion
            ),
            topology=topology,
        )
        if max(source_room, destination_room) > progress["current_room"]:
            raise ValueError("Dungeon next room has no committed victory authorization")
        if destination_room > source_room:
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

    def transition(allowed_accounts=None):
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
