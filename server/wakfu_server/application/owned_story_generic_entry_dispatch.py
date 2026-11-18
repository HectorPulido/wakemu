"""Native generic entry uses the common party position fence and travel outbox."""

import struct
import time


def _transition(app, selected, body, *, owned=False, operation_ticket=None):
    from wakfu_server import owned_story_generic_entry as entry
    from wakfu_server import dungeon_position_barrier, dungeon_runtime
    from wakfu_server.combat_terrain import map_geometry

    state, runtime = app.state, app.runtime

    def transition(accounts):
        current = runtime.STORE.character(state.account_id, state.character["id"])

        def initialize(db, session):
            dungeon_runtime.initialize_instance(
                db,
                session,
                groups=runtime.COMBAT_GROUPS,
                geometry=map_geometry(selected["route"]["start_map_id"]),
                store=runtime.STORE,
            )

        if owned:
            from wakfu_server import owned_story_generic_transfer
            from wakfu_server import owned_story_generic_return

            target_entry = owned_story_generic_transfer.enter
        else:
            target_entry = entry.enter
        extra = {} if owned else {"operation_ticket": operation_ticket}
        return target_entry(
            runtime.STORE,
            state.account_id,
            state.generation,
            current,
            body,
            loaded=state.loaded,
            blocked=(
                app.environment_blocked(allow_source=True)
                if operation_ticket is not None
                else app.environment_blocked()
            )
            or state.environment_ticket is not None,
            allowed_position_accounts=accounts,
            initialize_instance=initialize,
            resolve_destination=dungeon_runtime.entry_destination,
            **extra,
        )

    result = dungeon_position_barrier.run_party_entry(
        runtime.STORE,
        runtime.POSITIONS,
        state.account_id,
        state.character["id"],
        transition=transition,
    )
    if result.get("source_packets"):
        runtime.send_batch(state.connection, state.service, result["source_packets"])
    if operation_ticket is not None:
        state.quest_source_ticket = None
    app.deliver_dungeon_transitions(before_action=True)
    return True


def handle(app):
    from wakfu_server import owned_story_generic_entry as entry
    from wakfu_server import dungeon_runtime

    state, runtime = app.state, app.runtime
    if len(state.body) != 12:
        return False
    object_id, requested_action, _ = struct.unpack(">qHH", state.body)
    owned = state.character.get("instance_id", 0) != 0
    with runtime.STORE.connection() as db:
        if owned:
            from wakfu_server import owned_story_generic_transfer
            from wakfu_server import owned_story_generic_return

            _, source_configuration = dungeon_runtime.configuration_for_instance(
                db, state.character["instance_id"]
            )
            returning = owned_story_generic_return.selection(
                source_configuration, state.body
            )
            if returning is not None:
                if getattr(state, "quest_source_ticket", None) is not None:
                    return True
                with runtime.POSITIONS.account_barrier(state.account_id):
                    runtime.flush_positions(
                        account_id=state.account_id,
                        generation=state.generation,
                        character_id=state.character["id"],
                    )
                    state.quest_source_ticket = (
                        owned_story_generic_return.begin_operation(
                            runtime.STORE,
                            state.account_id,
                            state.generation,
                            state.character,
                            state.body,
                            loaded=state.loaded,
                            blocked=app.environment_blocked()
                            or state.environment_ticket is not None,
                        )
                    )
                return True
            if (
                owned_story_generic_transfer.selection(source_configuration, state.body)
                is None
            ):
                return False
        selected = entry.configuration(db, state.character["map_id"], object_id)
    if selected is None:
        if owned:
            raise ValueError(
                "Owned generic transfer's independently published destination is missing"
            )
        return False

    _, group, action, _, _, _ = entry.validate_route(selected["route"])
    if requested_action != action["wire_action"]:
        return False
    if group["cog"]:
        if owned:
            raise ValueError(
                "Timed generic transfers between owned contexts are unavailable"
            )
        if getattr(state, "quest_source_ticket", None) is not None:
            return True
        with runtime.POSITIONS.account_barrier(state.account_id):
            runtime.flush_positions(
                account_id=state.account_id,
                generation=state.generation,
                character_id=state.character["id"],
            )
            state.quest_source_ticket = entry.begin_operation(
                runtime.STORE,
                state.account_id,
                state.generation,
                state.character,
                state.body,
                loaded=state.loaded,
                blocked=app.environment_blocked()
                or state.environment_ticket is not None,
            )
        return True
    return _transition(app, selected, state.body, owned=owned)


def poll(app):
    """Reuse the source-operation clock, then enter through normal travel fences."""
    from wakfu_server import owned_story_generic_entry as entry

    state, runtime = app.state, app.runtime
    ticket = getattr(state, "quest_source_ticket", None)
    if not isinstance(ticket, dict) or ticket.get("schema") != entry.OPERATION_SCHEMA:
        return False
    if time.monotonic() < getattr(state, "quest_source_poll_after", 0):
        return False
    if int(runtime.STORE.now().timestamp() * 1000) < ticket["due_ms"]:
        return False
    from psycopg import Error as DatabaseError
    from psycopg_pool import PoolTimeout

    try:
        if ticket.get("operation_kind") == "owned_generic_return":
            from wakfu_server import owned_story_generic_return
            from wakfu_server import dungeon_position_barrier

            dungeon_position_barrier.run_account_exit(
                runtime.STORE,
                runtime.POSITIONS,
                state.account_id,
                defer_rebind_busy=True,
                transition=lambda: owned_story_generic_return.complete_operation(
                    runtime.STORE,
                    state.account_id,
                    state.generation,
                    state.character,
                    ticket,
                    loaded=state.loaded,
                    blocked=app.environment_blocked(allow_source=True)
                    or state.environment_ticket is not None,
                ),
            )
            state.quest_source_ticket = None
            app.deliver_dungeon_transitions(before_action=True)
            return True
        body = bytes.fromhex(ticket["body_hex"])
        object_id = struct.unpack(">qHH", body)[0]
        with runtime.STORE.connection() as db:
            selected = entry.configuration(db, state.character["map_id"], object_id)
        if selected is None:
            raise ValueError("Timed generic destination publication is unavailable")
        _transition(app, selected, body, operation_ticket=ticket)
        state.quest_source_ticket = None
        return True
    except (DatabaseError, PoolTimeout) as error:
        state.quest_source_poll_after = time.monotonic() + 1
        runtime.record(
            event="owned_generic_entry_operation_retry",
            actor_id=state.character["id"],
            reason=type(error).__name__,
        )
        return False
    except ValueError as error:
        state.quest_source_ticket = None
        runtime.record(
            event="owned_generic_entry_operation_cancelled",
            actor_id=state.character["id"],
            reason=str(error),
        )
        return False
