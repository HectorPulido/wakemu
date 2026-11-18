"""Source quest actions reuse the normal owned session and combat constructor."""

import struct
import time


def _apply(session, result):
    state, runtime = session.state, session.runtime
    state.character = result["character"]
    if result.get("relocated"):
        state.position = {key: state.character[key] for key in ("x", "y", "z")}
        state.movement_state = runtime.Movement(state.position)
        runtime.POSITIONS.rebind_selected(
            state.account_id, state.generation, state.character["id"]
        )
        for packet in result["packets"]:
            if packet[0] == 13530:
                runtime.WORLD.update(
                    state.generation, state.character, *packet, include_sender=False
                )
        session.mark_static_sync_pending()
    state.quest_source_ticket = result.get("ticket")
    if result["packets"]:
        session.publish_settled_quest_packets(result["packets"])
    target = result["target"]
    if target is None:
        return
    runtime.send(state.connection, state.service, *result["scene_packet"])
    # Reuse the normal session dispatch queue, so request-local admission
    # fields are initialized through the same path as a genuine attack.
    state.pending_guardian_attack = struct.pack(
        ">qiihB", target["id"], target["x"], target["y"], target["z"], 0
    )


def handle(session):
    from wakfu_server.achievements import source_quest_encounters

    state, runtime = session.state, session.runtime
    if not source_quest_encounters.recognizes(state.character["map_id"], state.body):
        return False
    if getattr(state, "quest_source_ticket", None) is not None:
        return True
    from psycopg import Error as DatabaseError
    from psycopg_pool import PoolTimeout
    from wakfu_server.ecology_feedback import information

    try:
        with runtime.POSITIONS.account_barrier(state.account_id):
            runtime.flush_positions(
                account_id=state.account_id,
                generation=state.generation,
                character_id=state.character["id"],
            )
            result = source_quest_encounters.interact(
                runtime.STORE,
                runtime.COMBAT_GROUPS,
                state.account_id,
                state.generation,
                state.character,
                state.body,
                loaded=state.loaded,
                blocked=session.environment_blocked()
                or state.environment_ticket is not None,
                approved_positions=tuple(
                    getattr(getattr(state, "movement_state", None), "approved", ())
                ),
            )
            if not result["handled"]:
                return False
            _apply(session, result)
            return True
    except (ValueError, DatabaseError, PoolTimeout) as error:
        runtime.record(
            event="quest_source_interaction_rejected",
            actor_id=state.character["id"],
            reason=(
                str(error) if isinstance(error, ValueError) else type(error).__name__
            ),
        )
        runtime.send(
            state.connection,
            state.service,
            *information(
                "This interaction is unavailable. Move next to the object and try again."
            ),
        )
        return True


def poll(session):
    """Finish the reviewed source delay; untouched sessions do no extra SQL."""
    state, runtime = session.state, session.runtime
    ticket = getattr(state, "quest_source_ticket", None)
    if (
        isinstance(ticket, dict)
        and ticket.get("schema") == "owned-generic-entry-ticket-v1"
    ):
        from . import owned_story_generic_entry_dispatch

        return owned_story_generic_entry_dispatch.poll(session)
    if ticket is None or time.monotonic() < getattr(
        state, "quest_source_poll_after", 0
    ):
        return False
    if (
        int(runtime.STORE.now().timestamp() * 1000) < ticket["due_ms"]
        and getattr(state, "quest_source_opening_ack", None) != ticket["token"]
    ):
        return False
    from psycopg import Error as DatabaseError
    from psycopg_pool import PoolTimeout
    from wakfu_server.achievements import source_quest_encounters

    try:
        with runtime.POSITIONS.account_barrier(state.account_id):
            runtime.flush_positions(
                account_id=state.account_id,
                generation=state.generation,
                character_id=state.character["id"],
            )
            result = source_quest_encounters.complete_operation(
                runtime.STORE,
                runtime.COMBAT_GROUPS,
                state.account_id,
                state.generation,
                state.character,
                ticket,
                loaded=state.loaded,
                blocked=session.environment_blocked(allow_source=True)
                or state.environment_ticket is not None,
            )
            _apply(session, result)
        return True
    except (DatabaseError, PoolTimeout) as error:
        state.quest_source_poll_after = time.monotonic() + 1
        runtime.record(
            event="quest_source_operation_retry",
            actor_id=state.character["id"],
            reason=str(error),
        )
        return False
    except ValueError as error:
        state.quest_source_ticket = None
        runtime.record(
            event="quest_source_operation_cancelled",
            actor_id=state.character["id"],
            reason=str(error),
        )
        return False


def handle_callback(session, event):
    """A matching offered movie can end early; this grants no quest victory."""
    state, runtime = session.state, session.runtime
    ticket = getattr(state, "quest_source_ticket", None)
    if ticket is None or ticket.get("opening_shown") is not True:
        return False
    from wakfu_server.achievements import source_quest_encounters as source

    row = next(
        (r for r in source._all_bindings() if r["id"] == ticket.get("binding")), None
    )
    opening = None if row is None else (row.get("scenario") or {}).get("opening")
    if opening is None or event != opening["event"]:
        return False
    with runtime.POSITIONS.account_barrier(state.account_id):
        runtime.flush_positions(
            account_id=state.account_id,
            generation=state.generation,
            character_id=state.character["id"],
        )
        source.acknowledge_opening(
            runtime.STORE,
            state.account_id,
            state.generation,
            state.character,
            ticket,
            event,
        )
    state.quest_source_opening_ack = ticket["token"]
    state.quest_source_poll_after = 0
    poll(session)
    return True
