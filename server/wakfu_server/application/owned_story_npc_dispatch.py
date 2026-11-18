"""Narrow session bridge for native owner-scoped story conversations."""

from wakfu_server import owned_story_npcs


def handle(session):
    from wakfu_server import owned_story_actor_operations

    if owned_story_actor_operations.handle(session):
        return True
    state, runtime = session.state, session.runtime
    if state.character is None or not owned_story_npcs.recognizes(
        runtime.STORE,
        state.opcode,
        state.body,
        state.npc_dialogue_session,
        state.character,
    ):
        return False
    if (
        not state.loaded
        or state.fight is not None
        or state.spectator_session is not None
        or state.environment_ticket is not None
        or session.environment_blocked()
    ):
        raise ValueError("Owned story conversation requires a ready idle owner")
    with runtime.POSITIONS.account_barrier(state.account_id):
        runtime.flush_positions(
            account_id=state.account_id,
            generation=state.generation,
            character_id=state.character["id"],
        )
        if state.opcode == 12058:
            result = owned_story_npcs.choose(
                runtime.STORE,
                state.account_id,
                state.generation,
                state.character,
                state.npc_dialogue_session,
                state.body,
            )
            state.character = result["character"]
            packets = result["packets"]
        else:
            actor_id, action_id = owned_story_npcs.npc_world.decode_interaction(
                state.body
            )
            from wakfu_server.npc_approach_target import approach_cells
            from wakfu_server.combat_geometry import prepare_geometry
            from wakfu_server.combat_terrain import map_geometry

            with runtime.STORE.connection() as db:
                current = runtime.STORE.character(
                    state.account_id, state.character["id"], db
                )
                row = next(
                    (
                        row
                        for row in owned_story_npcs.rows(db, runtime.STORE, current)
                        if row["actor_id"] == actor_id
                        and action_id in row["action_ids"]
                    ),
                    None,
                )
            if row is None:
                raise ValueError("Owned story NPC is not available in this scene")
            state.character = current
            geometry = prepare_geometry(map_geometry(row["map_id"]))
            goals = approach_cells(geometry, row)
            if session.approach_actor(goals.__contains__, geometry=geometry):
                return True
            if state.npc_dialogue_session is not None:
                state.npc_dialogue_session.close()
            state.npc_dialogue_session, packets = owned_story_npcs.begin(
                runtime.STORE,
                state.account_id,
                state.generation,
                state.character,
                actor_id,
                action_id,
            )
            if state.npc_dialogue_session is None:
                from . import owned_story_dispatch

                with runtime.STORE.connection() as db:
                    result = owned_story_dispatch._result(
                        db,
                        runtime.STORE,
                        state.character,
                        dict(applied=bool(packets), packets=packets, step=None),
                    )
                # Direct native actions can auto-complete an already-seen
                # scene and move its owner. Use the normal registry/CAS path.
                owned_story_dispatch.publish(session, result)
                return True
        session.publish_settled_quest_packets(packets)
        if state.opcode == 12058 and result.get("story_confirmed", False):
            from . import owned_story_dispatch

            owned_story_dispatch.refresh_group(session)
    return True
