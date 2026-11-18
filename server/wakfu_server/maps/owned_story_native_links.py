"""Pinned native portal links within a story, including its physical departure.

The real native source/approach, literal endpoint, item predicates and earned
mechanical frontier remain authoritative. This never clears ordinary doors or
turns a client-selected destination into mission completion by itself.
"""

import struct

from wakfu_server import generic_transports, owned_story_controller as controller
from wakfu_server.dungeon_runtime_config import canonical_hash


def declarations(selected):
    links = selected.get("native_links", [])
    steps = {step["id"] for step in selected["steps"]}
    seen = set()
    if not isinstance(links, list):
        raise ValueError("Owned story native links must be explicit")
    for link in links:
        if (
            not isinstance(link, dict)
            or set(link) != {"source_id", "destination_id", "requires"}
            or any(
                type(link.get(key)) is not int or link[key] <= 0
                for key in ("source_id", "destination_id")
            )
            or not isinstance(link["requires"], list)
            or len(set(link["requires"])) != len(link["requires"])
            or not set(link["requires"]) <= steps
            or (link["source_id"], link["destination_id"]) in seen
        ):
            raise ValueError("Invalid or ambiguous owned native link")
        seen.add((link["source_id"], link["destination_id"]))
    return links


def validate_sources(selected, native):
    frozen = native.get("teleporters", {})
    for link in declarations(selected):
        source = generic_transports.source(selected["map_id"], link["source_id"])
        if source is None or source != frozen.get(str(link["source_id"])):
            raise ValueError("Owned native portal differs from its pinned source")
        choices = [
            row
            for row in source["destinations"]
            if row["destination_id"] == link["destination_id"]
        ]
        if (
            len(choices) != 1
            or choices[0]["cyZ"] >= 0
            or choices[0]["cyX"] != 0
            or choices[0]["cyW"] != 0
            or choices[0]["native_altitude_walkable"] is not True
        ):
            raise ValueError("Owned native portal lost its exact free native endpoint")


def selected_link(selected, body):
    if not isinstance(body, (bytes, bytearray, memoryview)) or len(body) != 17:
        raise ValueError("Malformed owned native portal request")
    source, destination, flag, mode = struct.unpack(">qiBi", body)
    rows = [
        row
        for row in declarations(selected)
        if (row["source_id"], row["destination_id"]) == (source, destination)
    ]
    if not rows:
        return None
    if (flag, mode) != (0, 2):
        raise ValueError("Unsupported owned native portal mode")
    return rows[0]


def travel(
    db, store, account_id, generation, character, body, *, source_allowed, in_fight
):
    from wakfu_server import (
        dungeon_criteria,
        dungeon_exit,
        owned_story_mechanics as mechanics,
    )
    from wakfu_server.owned_story_gameplay_states import has_state

    selected, completed = controller._scope(db, store, character)
    link = selected_link(selected, body)
    if link is None:
        return None
    if in_fight(character["id"]) is not False:
        raise ValueError("Leave combat before using a native story portal")
    native = mechanics.sources(selected)
    validate_sources(selected, native)
    source = generic_transports.source(character["map_id"], link["source_id"])
    target = next(
        row
        for row in source["destinations"]
        if row["destination_id"] == link["destination_id"]
    )
    if not set(link["requires"]) <= completed:
        raise ValueError("Clear the blocking encounter before using this portal")
    if source_allowed(character, dict(source)) is not True:
        raise ValueError("Owned native portal is outside its exact original approach")
    if not dungeon_criteria.evaluate(
        store,
        target["criterion"],
        character=character,
        queries={"HasState": lambda state: has_state(character, state)},
        bypass_mission_prerequisites=True,
    ):
        raise ValueError("Owned native portal item or world condition is not fulfilled")
    outcome = controller._settle(
        db,
        store,
        character,
        selected,
        completed,
        kind="native_travel",
        reference=link["destination_id"],
        evidence=dict(
            source_id=source["id"],
            destination_id=target["destination_id"],
            source_sha256=canonical_hash(source),
            source_position=[character[key] for key in ("x", "y", "z")],
        ),
        apply_effects=mechanics.executor(selected),
    )
    if target["map_id"] == character["map_id"]:
        outcome["packets"].append(
            mechanics.move(
                db,
                character,
                [target[key] for key in ("x", "y", "z")],
                direction=target["direction"],
            )
        )
        outcome["applied"] = True
        return dict(internal=True, outcome=outcome)
    from wakfu_server import owned_cinematic_continuations
    from wakfu_server.achievements import storage

    continuation = owned_cinematic_continuations.policy(selected)
    if (
        continuation is not None
        and owned_cinematic_continuations.recognizes(selected, body)
        and owned_cinematic_continuations.eligible(
            continuation, storage.load_locked(db, character["id"])
        )
    ):
        owned_cinematic_continuations.begin(
            db,
            store,
            account_id,
            generation,
            character["id"],
            body,
            source_allowed=source_allowed,
            in_fight=in_fight,
        )
        return dict(internal=False, outcome=outcome)
    destination = {key: target[key] for key in ("map_id", "x", "y", "z")}
    dungeon_exit._leave(
        store,
        account_id,
        generation,
        character["id"],
        in_fight=in_fight,
        destination_for=lambda *_: destination,
        _db=db,
    )
    return dict(internal=False, outcome=outcome)


def handle_session(session, *, source_allowed, in_fight):
    """Use the existing position barrier and normal committed presentation path."""
    from wakfu_server.application import owned_story_dispatch

    state, runtime = session.state, session.runtime
    with runtime.POSITIONS.account_barrier(state.account_id):
        runtime.flush_positions(
            account_id=state.account_id,
            generation=state.generation,
            character_id=state.character["id"],
        )
        with runtime.STORE.connection() as db:
            current = runtime.STORE.character(
                state.account_id, state.character["id"], db
            )
            result = travel(
                db,
                runtime.STORE,
                state.account_id,
                state.generation,
                current,
                state.body,
                source_allowed=source_allowed,
                in_fight=in_fight,
            )
            if result is None:
                raise ValueError("Owned native link changed before its transaction")
            presentation = (
                owned_story_dispatch._result(
                    db, runtime.STORE, current, result["outcome"]
                )
                if result["internal"]
                else None
            )
        runtime.POSITIONS.rebind_selected(
            state.account_id, state.generation, state.character["id"]
        )
        if presentation is not None:
            owned_story_dispatch.publish(session, presentation)
    if presentation is None:
        # The durable leave already rebound the destination. Publish committed
        # deltas directly; refreshing reward state against the stale source
        # character here would merge old coordinates into the new baseline.
        runtime.send_batch(
            state.connection, state.service, result["outcome"]["packets"]
        )
        session.deliver_dungeon_transitions(before_action=True)
    else:
        owned_story_dispatch.refresh_group(session)
    return True
