"""Pinned native GenericActivable coordinate programs entering owned content.

The actual 12870 action is authenticated directly. No teleporter request or
remote interactive identity is synthesized for the common entry transaction.
"""

import struct
import secrets
from contextlib import nullcontext

KIND = "native_generic_choice"
OPERATION_SCHEMA = "owned-generic-entry-ticket-v1"


def validate_approaches(source, approaches):
    """Qualify frozen QV cells without replacing original heights or directions."""
    from wakfu_server.combat_geometry import published_geometry
    from wakfu_server.native_interaction_approaches import _DIRECTIONS, _RELATIVE

    if (
        source.get("type") != "GenericActivableInteractiveElement"
        or not isinstance(approaches, list)
        or not approaches
        or any(
            not isinstance(point, list)
            or len(point) != 3
            or any(type(v) is not int for v in point)
            for point in approaches
        )
    ):
        raise ValueError(
            "Native generic approaches require their explicit original cells"
        )
    payload = bytes.fromhex(source["payload_hex"])
    floors = published_geometry(source["map_id"]).cells
    mask = struct.unpack_from(">H", payload, 31)[0]
    orientation = payload[30]
    if mask > 511 or orientation >= 8:
        raise ValueError("Generic owned entrance has invalid native approach flags")
    offsets = {(0, 0)} if mask & 256 else set()
    offsets.update(
        _DIRECTIONS[(orientation + relative) % 8]
        for bit, relative in _RELATIVE
        if mask & bit
    )
    if any(
        tuple(point) not in floors
        or (point[0] - source["x"], point[1] - source["y"]) not in offsets
        or abs(point[2] - source["z"]) > 4
        for point in approaches
    ):
        raise ValueError(
            "Generic owned entrance approaches leave its actual native floor"
        )
    return frozenset(map(tuple, approaches))


def validate_entry(entry, *, cells=None):
    from wakfu_server import world_static
    from wakfu_server.exploration_artifact_actions import _teleport

    required = {
        "kind",
        "source",
        "program",
        "wire_action",
        "effect_reference",
        "approaches",
        "evidence",
    }
    scripted = entry.get("scripted_trial") if isinstance(entry, dict) else None
    if (
        not isinstance(entry, dict)
        or set(entry)
        != required | ({"scripted_trial"} if scripted is not None else set())
        or entry["kind"] != KIND
        or not entry["evidence"]
    ):
        raise ValueError("Generic owned entrance lacks its explicit native declaration")
    source, program = entry["source"], entry["program"]
    actual = next(
        (
            row
            for row in world_static.objects(source["map_id"])
            if row["id"] == source["id"]
        ),
        None,
    )
    if actual is None or any(
        actual.get(key) != source.get(key)
        for key in (
            "map_id",
            "id",
            "type",
            "x",
            "y",
            "z",
            "payload_hex",
            "chunk",
            "auto",
        )
    ):
        raise ValueError("Generic owned entrance differs from the actual native source")
    payload = bytes.fromhex(source["payload_hex"])
    # Native bEG generic payload: the parameter string follows the fixed
    # 33-byte interactive header, prefixed by its original signed int length.
    parameter_length = struct.unpack_from(">i", payload, 33)[0]
    if not 0 < parameter_length <= 64 or 37 + parameter_length > len(payload):
        raise ValueError("Generic owned entrance has no native parameter string")
    native_parameter = payload[37 : 37 + parameter_length].decode("ascii")
    if (
        source["type"] != "GenericActivableInteractiveElement"
        or str(program.get("descriptor_id")) != native_parameter
        or str(source.get("native_parameters")) != native_parameter
    ):
        raise ValueError("Generic owned entrance lost its native descriptor")
    choices = [
        (group, action, effect)
        for group in program["groups"]
        for action in group["actions"]
        for effect in action["effects"]
        if action["wire_action"] == entry["wire_action"]
        and effect["action_reference"] == entry["effect_reference"]
        and effect["effect_type"] == (1 if scripted is not None else 3)
    ]
    if len(choices) != 1:
        raise ValueError(
            "Generic owned entrance requires one literal native coordinate effect"
        )
    group, action, effect = choices[0]
    if len(action["effects"]) != 1:
        raise ValueError(
            "Generic owned entrance requires one immediate native coordinate program"
        )
    if (
        group["cnd"] != 0
        or type(group["cog"]) is not int
        or not 0 <= group["cog"] <= 60000
        or action["raw_cob"] != 1.0
    ):
        raise ValueError("Generic owned entrance has unsupported native occupation")
    if scripted is None:
        target, direction, delay = _teleport(effect)
    else:
        # A native script invocation has no coordinate destination. Its current
        # server implementation is an explicit reviewed source-bound join,
        # never presented as an original teleporter definition.
        if (
            type(scripted) is not dict
            or set(scripted) != {"schema", "map_id", "arrival", "direction", "evidence"}
            or scripted["schema"] != "owned-native-script-entry-v1"
            or scripted["map_id"] != source["map_id"]
            or type(scripted["arrival"]) is not list
            or len(scripted["arrival"]) != 3
            or any(type(v) is not int for v in scripted["arrival"])
            or type(scripted["direction"]) is not int
            or not 0 <= scripted["direction"] < 8
            or type(scripted["evidence"]) is not str
            or not scripted["evidence"].strip()
            or effect["parameters"] not in ([], ["false"])
        ):
            raise ValueError(
                "Native script entry lacks its reviewed actual terrain join"
            )
        target = dict(
            map_id=scripted["map_id"], **dict(zip(("x", "y", "z"), scripted["arrival"]))
        )
        direction, delay = scripted["direction"], 0
    if (
        delay
        or not isinstance(entry["approaches"], list)
        or not entry["approaches"]
        or any(
            not isinstance(point, list)
            or len(point) != 3
            or any(type(v) is not int for v in point)
            for point in entry["approaches"]
        )
    ):
        raise ValueError(
            "Generic owned entrance needs immediate native travel and reviewed approaches"
        )
    if cells is not None and [target[k] for k in ("x", "y", "z")] not in cells:
        raise ValueError("Generic owned entrance is outside actual native terrain")
    validate_approaches(source, entry["approaches"])
    return source, group, action, effect, target, direction


def validate_route(route):
    proof = validate_entry(route["native_generic_entry"])
    source, _, _, effect, target, _ = proof
    if (
        route["registration_policy"] != KIND
        or route["entry_map_id"] != source["map_id"]
        or route["entry_object_id"] != source["id"]
        or route["destination_id"] != effect["action_reference"]
        or route["start_map_id"] != target["map_id"]
        or route["criterion"] != effect["criterion"]
        or route.get("native_template_id") is not None
        or route.get("native_definition_id") is not None
    ):
        raise ValueError("Generic owned route differs from its native effect")
    return proof


def configuration(db, map_id, object_id):
    from wakfu_server import dungeon_instances

    keys = [
        dungeon_instances.canonical_context_key(row)
        for row in dungeon_instances.routes_for_object(map_id, object_id)
    ]
    if not keys:
        return None
    rows = db.execute(
        "SELECT c.configuration FROM dungeon_runtime_active_configurations a "
        "JOIN dungeon_runtime_configurations c ON c.route_key=a.route_key AND c.policy_version=a.policy_version "
        "WHERE a.route_key=ANY(%s) AND c.configuration->'route'->>'registration_policy'=%s",
        (keys, KIND),
    ).fetchall()
    if len(rows) > 1:
        raise ValueError("Ambiguous published native generic entrance")
    return rows[0]["configuration"] if rows else None


def enter(
    store,
    account_id,
    generation,
    character,
    body,
    *,
    loaded,
    blocked,
    allowed_position_accounts,
    initialize_instance=None,
    resolve_destination=None,
    operation_ticket=None,
    _db=None,
):
    from wakfu_server import dungeon_instances, dungeon_transport, dungeon_criteria
    from wakfu_server.simple_item_actions import _idle
    from wakfu_server.achievements import storage
    from wakfu_server.dungeon_achievement_authority import queries_from_state

    if type(body) is not bytes or len(body) != 12 or not loaded or blocked:
        raise ValueError("Generic owned entry requires its loaded idle native action")
    if allowed_position_accounts is None or account_id not in allowed_position_accounts:
        raise ValueError("Generic owned entrance escaped its actual position fence")
    identity, action_id, parameter = struct.unpack(">qHH", body)
    with store.connection() if _db is None else nullcontext(_db) as db:
        db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account_id,))
        store.lock_character(db, account_id, generation, character["id"], selected=True)
        actual = store.character(account_id, character["id"], db)
        _idle(db, actual["id"], store.now())
        if actual.get("instance_id", 0) != 0 or any(
            actual[k] != character[k] for k in ("map_id", "instance_id", "x", "y", "z")
        ):
            raise ValueError("Generic owned entrance lost its public source position")
        selected = configuration(db, actual["map_id"], identity)
        if selected is None:
            raise ValueError("Native generic owned entrance is not published")
        source, group, action, effect, target, direction = validate_route(
            selected["route"]
        )
        metadata = selected["route"]["native_generic_entry"]
        if (
            parameter
            or source["id"] != identity
            or source["map_id"] != actual["map_id"]
            or action_id != action["wire_action"]
            or [actual[k] for k in ("x", "y", "z")] not in metadata["approaches"]
        ):
            raise ValueError(
                "Generic owned entrance is outside its actual native action/approach"
            )
        if group["cog"]:
            require_operation(
                db,
                store,
                actual,
                account_id,
                generation,
                selected,
                body,
                operation_ticket,
            )
        authority = queries_from_state(storage.load_locked(db, actual["id"]))
        if db.execute(
            "SELECT 1 FROM environment_interaction_tickets WHERE character_id=%s AND state='active'",
            (actual["id"],),
        ).fetchone():
            raise ValueError(
                "Generic owned entrance is occupied by another native action"
            )
        if group["cod"]:
            from wakfu_server.combat_inventory_date_conditions import (
                complete_owned_item_quantity,
            )

            if complete_owned_item_quantity(actual, (group["cod"],)) < group["coe"]:
                raise ValueError(
                    "Generic owned entrance requires its actual native item"
                )

        def allowed(current, expression):
            return dungeon_criteria.evaluate(
                store,
                expression,
                character=current,
                queries=authority,
                bypass_mission_prerequisites=True,
            )

        if not allowed(actual, action["criterion"]):
            raise ValueError("Native generic action's world or item condition failed")
        route = dungeon_instances.route(selected["route"]["key"])
        result = dungeon_transport.enter_resolved(
            store,
            account_id,
            generation,
            actual["id"],
            dict(
                route=route,
                source=source,
                difficulty_selection=None,
                native_destination=dict(
                    cyW=group["coe"] if group["cod"] and group["cof"] else 0,
                    item_reference=group["cod"],
                ),
                destination=dict(target, direction=direction),
            ),
            criterion_allowed=allowed,
            source_allowed=lambda current, bound: bound == source
            and current["map_id"] == source["map_id"]
            and current.get("instance_id", 0) == 0
            and [current[k] for k in ("x", "y", "z")] in metadata["approaches"],
            initialize_instance=initialize_instance,
            resolve_destination=resolve_destination,
            allowed_position_accounts=allowed_position_accounts,
            _db=db,
        )
        if group["cog"]:
            storage.record_event(
                db,
                actual["id"],
                "owned-generic-entry-ended:" + operation_ticket["token"],
                dict(
                    schema=OPERATION_SCHEMA,
                    token=operation_ticket["token"],
                    owner=actual["id"],
                    cancelled=False,
                ),
            )
        return result


def begin_operation(store, account_id, generation, character, body, *, loaded, blocked):
    """Pin a real timed source action; no travel, cost or objective settles yet."""
    from wakfu_server import dungeon_runtime_config
    from wakfu_server.achievements import storage
    from wakfu_server.paid_containers import _leased_owner
    from wakfu_server.simple_item_actions import _idle
    from wakfu_server.dungeon_achievement_authority import queries_from_state
    from wakfu_server import dungeon_criteria

    if not isinstance(body, bytes) or len(body) != 12 or not loaded or blocked:
        raise ValueError("Timed generic entry requires a loaded idle source action")
    identity, wire_action, parameter = struct.unpack(">qHH", body)
    with store.connection() as db:
        _leased_owner(store, db, account_id, generation, character)
        actual = store.character(account_id, character["id"], db)
        _idle(db, actual["id"], store.now())
        selected = configuration(db, actual["map_id"], identity)
        if selected is None:
            raise ValueError("Timed generic entrance is not published")
        source, group, action, _, _, _ = validate_route(selected["route"])
        if group["cog"] == 0:
            return None
        metadata = selected["route"]["native_generic_entry"]
        if (
            actual.get("instance_id", 0) != 0
            or parameter
            or wire_action != action["wire_action"]
            or any(
                actual[key] != character[key]
                for key in ("map_id", "instance_id", "x", "y", "z")
            )
            or [actual[key] for key in ("x", "y", "z")] not in metadata["approaches"]
            or db.execute(
                "SELECT 1 FROM environment_interaction_tickets "
                "WHERE character_id=%s AND state='active'",
                (actual["id"],),
            ).fetchone()
        ):
            raise ValueError(
                "Timed generic entry lost its exact source action or position"
            )
        authority = queries_from_state(storage.load_locked(db, actual["id"]))
        if not dungeon_criteria.evaluate(
            store,
            action["criterion"],
            character=actual,
            queries=authority,
            bypass_mission_prerequisites=True,
        ):
            raise ValueError("Timed generic action condition failed")
        ticket = dict(
            schema=OPERATION_SCHEMA,
            token=secrets.token_hex(16),
            account_id=account_id,
            generation=str(generation),
            owner=actual["id"],
            route_key=selected["route"]["key"],
            route_sha256=dungeon_runtime_config.canonical_hash(selected["route"]),
            body_hex=body.hex(),
            position={
                key: actual[key] for key in ("map_id", "instance_id", "x", "y", "z")
            },
            due_ms=int(store.now().timestamp() * 1000) + group["cog"],
        )
        if not storage.record_event(
            db, actual["id"], "owned-generic-entry-start:" + ticket["token"], ticket
        ):
            raise ValueError("Timed generic source operation token collided")
        return ticket


def require_operation(
    db, store, character, account_id, generation, selected, body, ticket
):
    """A timed entrance consumes only its own due server-issued operation."""
    from wakfu_server import dungeon_runtime_config

    if (
        not isinstance(ticket, dict)
        or ticket.get("schema") != OPERATION_SCHEMA
        or type(ticket.get("token")) is not str
        or len(ticket["token"]) != 32
        or any(char not in "0123456789abcdef" for char in ticket["token"])
        or (ticket.get("account_id"), ticket.get("generation"), ticket.get("owner"))
        != (account_id, str(generation), character["id"])
        or ticket.get("route_key") != selected["route"]["key"]
        or ticket.get("route_sha256")
        != dungeon_runtime_config.canonical_hash(selected["route"])
        or ticket.get("body_hex") != body.hex()
        or type(ticket.get("due_ms")) is not int
        or int(store.now().timestamp() * 1000) < ticket["due_ms"]
        or ticket.get("position")
        != {key: character[key] for key in ("map_id", "instance_id", "x", "y", "z")}
    ):
        raise ValueError("Timed generic entrance lacks its due original operation")
    saved = db.execute(
        "SELECT payload FROM character_achievement_events "
        "WHERE character_id=%s AND event_key=%s",
        (character["id"], "owned-generic-entry-start:" + ticket["token"]),
    ).fetchone()
    ended = db.execute(
        "SELECT 1 FROM character_achievement_events "
        "WHERE character_id=%s AND event_key=%s",
        (character["id"], "owned-generic-entry-ended:" + ticket["token"]),
    ).fetchone()
    if saved is None or saved["payload"] != ticket or ended is not None:
        raise ValueError(
            "Timed generic entrance operation is missing, changed or consumed"
        )
