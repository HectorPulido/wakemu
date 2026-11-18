"""Original timed GenericIE actions through the existing leased story executor.

The native client owns its original presentation. The server independently
waits the native duration and cancels on movement, reconnect or source change.
"""
from datetime import timedelta
import struct

from wakfu_server import owned_story_controller as controller
from wakfu_server import owned_story_mechanics as mechanics


def selection(db, store, character, body):
    if isinstance(body, bytes) and len(body) == 12:
        _, action, _ = struct.unpack(">qHH", body)
        if action != 0:
            return None
    inspected = controller.interact(
        db, store, character, body, apply_effects=None, inspect_only=True
    )
    selected, step = inspected["selected"], inspected["step"]
    if step is None:
        return None
    identity = struct.unpack_from(">q", body)[0]
    program = mechanics.sources(selected).get("programs", {}).get(str(identity))
    timed = (
        []
        if program is None
        else [
            (group, action)
            for group in program["groups"]
            for action in group["actions"]
            if action["wire_action"] == 0 and group.get("cog", 0) > 0
        ]
    )
    if not timed:
        return None
    groups = [
        (group, action)
        for group, action in timed
        if mechanics.allowed(db, store, character, action["criterion"])
        and all(
            mechanics.allowed(db, store, character, effect["criterion"])
            for effect in action["effects"]
        )
    ]
    if not groups:
        raise ValueError("Timed story object native prerequisites are not satisfied")
    if (
        len(groups) != 1
        or type(groups[0][0]["cog"]) is not int
        or not 0 < groups[0][0]["cog"] <= 300000
    ):
        raise ValueError("Timed story object lacks one exact native duration")
    return dict(
        duration_ms=groups[0][0]["cog"],
        source_sha256=selected["native_sources"]["sha256"],
        controller_id=selected["id"],
        step=step["id"],
    )


def begin(session):
    """Run under the ordinary account position barrier before normal effects."""
    state, runtime = session.state, session.runtime
    previous = getattr(state.connection, "owned_story_object_operation", None)
    if previous is not None and previous["body"] != state.body:
        state.connection.owned_story_object_operation = None
    if (
        not state.loaded
        or state.fight is not None
        or state.combat_session is not None
        or state.spectator_session is not None
        or state.environment_ticket is not None
        or session.environment_blocked()
    ):
        raise ValueError("Timed story object requires an idle ready owner")
    from wakfu_server.paid_containers import _leased_owner

    with runtime.STORE.connection() as db:
        _leased_owner(
            runtime.STORE, db, state.account_id, state.generation, state.character
        )
        current = runtime.STORE.character(state.account_id, state.character["id"], db)
        operation = selection(db, runtime.STORE, current, state.body)
    if operation is None:
        return False
    identity = dict(
        account_id=state.account_id,
        generation=state.generation,
        character_id=current["id"],
        map_id=current["map_id"],
        instance_id=current["instance_id"],
        position=[current[k] for k in ("x", "y", "z")],
    )
    previous = getattr(state.connection, "owned_story_object_operation", None)
    if (
        previous is not None
        and previous["identity"] == identity
        and previous["body"] == state.body
        and previous["operation"] == operation
    ):
        return True
    state.connection.owned_story_object_operation = dict(
        identity=identity,
        body=state.body,
        operation=operation,
        due_at=runtime.STORE.now() + timedelta(milliseconds=operation["duration_ms"]),
    )
    return True


def poll(session):
    state, runtime = session.state, session.runtime
    ticket = getattr(state.connection, "owned_story_object_operation", None)
    if ticket is None:
        return False
    identity, character = ticket["identity"], state.character
    if (
        character is None
        or not state.loaded
        or state.fight is not None
        or state.combat_session is not None
        or state.spectator_session is not None
        or state.environment_ticket is not None
        or (
            state.account_id,
            state.generation,
            character["id"],
            character["map_id"],
            character.get("instance_id"),
            [character[k] for k in ("x", "y", "z")],
        )
        != (
            identity["account_id"],
            identity["generation"],
            identity["character_id"],
            identity["map_id"],
            identity["instance_id"],
            identity["position"],
        )
    ):
        state.connection.owned_story_object_operation = None
        return False
    if runtime.STORE.now() < ticket["due_at"]:
        return False
    state.connection.owned_story_object_operation = None
    from wakfu_server.application import owned_story_dispatch

    with runtime.POSITIONS.account_barrier(state.account_id):
        runtime.flush_positions(
            account_id=state.account_id,
            generation=state.generation,
            character_id=identity["character_id"],
        )
        with runtime.STORE.connection() as db:
            current = runtime.STORE.character(
                state.account_id, identity["character_id"], db
            )
            if (
                current is None
                or any(current[k] != identity[k] for k in ("map_id", "instance_id"))
                or [current[k] for k in ("x", "y", "z")] != identity["position"]
            ):
                return False
            try:
                operation = selection(db, runtime.STORE, current, ticket["body"])
            except ValueError:
                return False
            if operation != ticket["operation"]:
                return False
        try:
            result = owned_story_dispatch.interact(
                runtime.STORE,
                state.account_id,
                state.generation,
                current,
                ticket["body"],
                loaded=state.loaded,
                blocked=session.environment_blocked(),
            )
        except ValueError as error:
            from wakfu_server.ecology_feedback import information

            runtime.record(
                event="owned_story_timed_object_rejected",
                actor_id=current["id"],
                reason=str(error),
            )
            session.publish_settled_quest_packets([information(str(error))])
            return False
        owned_story_dispatch.publish(session, result)
    return True
