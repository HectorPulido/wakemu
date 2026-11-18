"""Explicit native attendant actions reuse the original owned entrance route.

This adapter never manufactures a teleporter packet or bypasses a source cost.
The native NPC click, actual walking approach and fresh selected lease qualify
the normal party-fenced admission transaction and its durable delivery outbox.
"""


def _current(db, store, state):
    from wakfu_server.simple_item_actions import _idle

    db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (state.account_id,))
    store.lock_character(
        db, state.account_id, state.generation, state.character["id"], selected=True
    )
    current = store.character(state.account_id, state.character["id"], db)
    if (
        current is None
        or current.get("account_id") != state.account_id
        or current.get("id") != state.character["id"]
        or current.get("instance_id", 0) != 0
        or (current["map_id"], current.get("instance_id", 0))
        != (state.character["map_id"], state.character.get("instance_id", 0))
        or current.get("hp", 0) <= 0
    ):
        raise ValueError("Physical entrance lost its selected public owner")
    _idle(db, current["id"], store.now())
    return current


def handle(app):
    state, runtime = app.state, app.runtime
    if state.opcode != 13222:
        return False
    from wakfu_server import owned_physical_offers as offers

    if not offers.recognizes(state.opcode, state.body):
        return False
    from psycopg import Error as DatabaseError
    from psycopg_pool import PoolTimeout
    from wakfu_server.position_buffer import PositionOwnerBusy
    from wakfu_server import (
        dungeon_entry_access,
        dungeon_position_barrier,
        dungeon_runtime,
        dungeon_transport,
        npc_world,
        teleporter_approach,
    )
    from wakfu_server.combat_geometry import prepare_geometry
    from wakfu_server.combat_terrain import map_geometry

    try:
        if (
            state.character is None
            or not state.loaded
            or state.fight is not None
            or getattr(state, "combat_session", None) is not None
            or state.spectator_session is not None
            or state.bag_session is not None
            or state.environment_ticket is not None
            or app.environment_blocked()
        ):
            raise ValueError("Physical entrance requires a loaded idle owner")
        identity, action = npc_world.decode_interaction(state.body)
        with runtime.POSITIONS.account_barrier(state.account_id):
            runtime.flush_positions(
                account_id=state.account_id,
                generation=state.generation,
                character_id=state.character["id"],
            )
            with runtime.STORE.connection() as db:
                current = _current(db, runtime.STORE, state)
                _, resolved = offers.resolve(
                    db, runtime.STORE, current, identity, action
                )
            # Do not hold SQL locks while the normal movement producer walks.
            state.character = current
            source = resolved["source"]
            allowed = teleporter_approach.callback(
                state.movement_state, map_id=current["map_id"], instance_id=0
            )
            if allowed(current, source) is not True:
                goals = frozenset(
                    tuple(point[k] for k in ("x", "y", "z"))
                    for point in source["approach_positions"]
                )
                if app.approach_actor(
                    goals.__contains__,
                    geometry=prepare_geometry(map_geometry(current["map_id"])),
                ):
                    return True
                raise ValueError("Physical entrance is outside its native approach")

        def transition(allowed_accounts):
            with runtime.STORE.connection() as db:
                current = _current(db, runtime.STORE, state)
                _, actual = offers.resolve(db, runtime.STORE, current, identity, action)
                source = actual["source"]
                native_approach = teleporter_approach.callback(
                    state.movement_state, map_id=current["map_id"], instance_id=0
                )

                def source_allowed(actor, candidate):
                    return (
                        candidate == source
                        and native_approach(actor, candidate) is True
                    )

                def initialize(entry_db, owned_session):
                    dungeon_runtime.initialize_instance(
                        entry_db,
                        owned_session,
                        groups=runtime.COMBAT_GROUPS,
                        geometry=map_geometry(actual["route"].start_map_id),
                        store=runtime.STORE,
                    )

                return dungeon_transport.enter_resolved(
                    runtime.STORE,
                    state.account_id,
                    state.generation,
                    current["id"],
                    actual,
                    criterion_allowed=lambda actor, criterion: dungeon_entry_access.evaluate(
                        runtime.STORE,
                        criterion,
                        character=actor,
                        destination_map_id=actual["route"].start_map_id,
                    ),
                    source_allowed=source_allowed,
                    initialize_instance=initialize,
                    resolve_destination=dungeon_runtime.entry_destination,
                    allowed_position_accounts=allowed_accounts,
                    _db=db,
                )

        dungeon_position_barrier.run_party_entry(
            runtime.STORE,
            runtime.POSITIONS,
            state.account_id,
            state.character["id"],
            transition=transition,
        )
        app.deliver_dungeon_transitions(before_action=True)
    except (ValueError, DatabaseError, PoolTimeout, PositionOwnerBusy) as error:
        from wakfu_server.ecology_feedback import information

        runtime.record(
            event="owned_physical_offer_rejected",
            actor_id=None if state.character is None else state.character["id"],
            reason=type(error).__name__,
        )
        runtime.send(
            state.connection,
            state.service,
            *information(
                "This entrance is unavailable. Approach the entrance attendant and try again."
            ),
        )
    return True
