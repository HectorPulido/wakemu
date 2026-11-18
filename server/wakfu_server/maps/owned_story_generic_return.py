"""Source-qualified native GenericIE returns through the ordinary exit outbox."""

import secrets
import struct

from wakfu_server import owned_story_generic_entry as entry

KIND = "owned-native-generic-return-v1"
OPERATION = "owned_generic_return"


def selection(configuration, body):
    from wakfu_server.combat_geometry import published_geometry

    selected = configuration.get("topology", {}).get("owned_story_controller")
    rows = [] if selected is None else selected.get("generic_returns", [])
    if not rows:
        return None
    if not isinstance(body, bytes) or len(body) != 12:
        raise ValueError("Malformed native generic return")
    identity, action_id, parameter = struct.unpack(">qHH", body)
    matches = []
    for row in rows:
        if (
            not isinstance(row, dict)
            or set(row) != {"schema", "entry", "requires", "evidence"}
            or row["schema"] != KIND
            or not row["evidence"]
            or not isinstance(row["requires"], list)
            or not set(row["requires"]) <= {step["id"] for step in selected["steps"]}
        ):
            raise ValueError("Generic return lacks its finite native declaration")
        source, group, action, effect, target, direction = entry.validate_entry(
            row["entry"]
        )
        if (
            source["map_id"] != selected["map_id"]
            or target["map_id"] == selected["map_id"]
            or group["cod"]
            or group["coe"]
            or tuple(target[key] for key in ("x", "y", "z"))
            not in published_geometry(target["map_id"]).cells
        ):
            raise ValueError(
                "Native generic return is not a free actual public endpoint"
            )
        if (
            identity == source["id"]
            and action_id == action["wire_action"]
            and parameter == 0
        ):
            matches.append(
                dict(
                    declaration=row,
                    source=source,
                    group=group,
                    action=action,
                    effect=effect,
                    target=target,
                    direction=direction,
                )
            )
    if len(matches) > 1:
        raise ValueError("Ambiguous native generic return")
    return matches[0] if matches else None


def validate(selected):
    """Validate every declared source through its original native request tuple."""
    rows = selected.get("generic_returns", [])
    if not isinstance(rows, list):
        raise ValueError("Generic returns must be a finite native source list")
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("entry"), dict):
            raise ValueError("Generic return lacks its native entry metadata")
        metadata = row["entry"]
        try:
            body = struct.pack(
                ">qHH", metadata["source"]["id"], metadata["wire_action"], 0
            )
        except (KeyError, TypeError, struct.error) as error:
            raise ValueError(
                "Generic return lost its original action identity"
            ) from error
        if (
            selection(dict(topology=dict(owned_story_controller=selected)), body)
            is None
        ):
            raise ValueError("Generic return has no original action")
    return bool(rows)


def _authority(configuration, selected):
    return dict(
        route=dict(
            key=configuration["route"]["key"],
            native_generic_return=selected["declaration"],
        )
    )


def _context(db, store, account_id, generation, location, body):
    from wakfu_server import dungeon_runtime, dungeon_criteria
    from wakfu_server import owned_story_controller
    from wakfu_server.achievements import storage
    from wakfu_server.dungeon_achievement_authority import queries_from_state
    from wakfu_server.paid_containers import _leased_owner
    from wakfu_server.simple_item_actions import _idle

    _leased_owner(store, db, account_id, generation, location)
    character = store.character(account_id, location["id"], db)
    _idle(db, character["id"], store.now())
    if character.get("instance_id", 0) <= 0 or any(
        character[key] != location[key]
        for key in ("map_id", "instance_id", "x", "y", "z")
    ):
        raise ValueError("Native generic return lost its owned source position")
    _, configuration = dungeon_runtime.configuration_for_instance(
        db, character["instance_id"]
    )
    selected = selection(configuration, body)
    if selected is None:
        raise ValueError("No native generic return at this source")
    controller, completed = owned_story_controller._scope(db, store, character)
    if (
        not set(selected["declaration"]["requires"]) <= completed
        or [character[key] for key in ("x", "y", "z")]
        not in selected["declaration"]["entry"]["approaches"]
        or owned_story_controller.pending_scene(
            db, store, character, controller, completed
        )
        is not None
        or db.execute(
            "SELECT 1 FROM environment_interaction_tickets "
            "WHERE character_id=%s AND state='active'",
            (character["id"],),
        ).fetchone()
    ):
        raise ValueError("Native generic return is not unlocked at its actual approach")
    queries = queries_from_state(storage.load_locked(db, character["id"]))
    for criterion in (selected["action"]["criterion"], selected["effect"]["criterion"]):
        if not dungeon_criteria.evaluate(
            store,
            criterion,
            character=character,
            queries=queries,
            bypass_mission_prerequisites=True,
        ):
            raise ValueError("Native generic return world or item condition failed")
    return character, configuration, selected


def begin_operation(store, account_id, generation, location, body, *, loaded, blocked):
    from wakfu_server.achievements import storage
    from wakfu_server.dungeon_runtime_config import canonical_hash

    if not loaded or blocked:
        raise ValueError("Native generic return requires its ready idle owner")
    with store.connection() as db:
        character, configuration, selected = _context(
            db, store, account_id, generation, location, body
        )
        authority = _authority(configuration, selected)
        ticket = dict(
            schema=entry.OPERATION_SCHEMA,
            operation_kind=OPERATION,
            token=secrets.token_hex(16),
            account_id=account_id,
            generation=str(generation),
            owner=character["id"],
            route_key=authority["route"]["key"],
            route_sha256=canonical_hash(authority["route"]),
            body_hex=body.hex(),
            position={
                key: character[key] for key in ("map_id", "instance_id", "x", "y", "z")
            },
            due_ms=int(store.now().timestamp() * 1000) + selected["group"]["cog"],
        )
        if not storage.record_event(
            db, character["id"], "owned-generic-entry-start:" + ticket["token"], ticket
        ):
            raise ValueError("Native generic return operation token collided")
        return ticket


def complete_operation(
    store, account_id, generation, location, ticket, *, loaded, blocked
):
    from wakfu_server import dungeon_exit
    from wakfu_server.achievements import storage

    if (
        not loaded
        or blocked
        or not isinstance(ticket, dict)
        or ticket.get("operation_kind") != OPERATION
    ):
        raise ValueError("Native generic return lacks its ready original operation")
    body = bytes.fromhex(ticket["body_hex"])
    with store.connection() as db:
        character, configuration, selected = _context(
            db, store, account_id, generation, location, body
        )
        entry.require_operation(
            db,
            store,
            character,
            account_id,
            generation,
            _authority(configuration, selected),
            body,
            ticket,
        )
        result = dungeon_exit._leave(
            store,
            account_id,
            generation,
            character["id"],
            in_fight=lambda _identity: False,
            destination_for=lambda *_: selected["target"],
            _db=db,
        )
        storage.record_event(
            db,
            character["id"],
            "owned-generic-entry-ended:" + ticket["token"],
            dict(
                schema=entry.OPERATION_SCHEMA,
                token=ticket["token"],
                owner=character["id"],
                cancelled=False,
            ),
        )
        return result
