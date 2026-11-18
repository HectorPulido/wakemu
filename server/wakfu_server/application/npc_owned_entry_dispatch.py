"""Actual native dialogue choices using the shared owned-entry position fence."""


def handle(app):
    from wakfu_server import quest_npc, npc_dialogue, dungeon_position_barrier
    from wakfu_server import dungeon_runtime, owned_story_npc_entry
    from wakfu_server.combat_terrain import map_geometry

    state, runtime = app.state, app.runtime
    session = state.npc_dialogue_session
    if (
        state.opcode != npc_dialogue.CHOICE_REQUEST
        or session is None
        or not hasattr(session, "quest_publication_sha256")
    ):
        return False
    route, paired = quest_npc.selected_choice_journey(
        runtime.STORE, session, state.body
    )
    if route is None and paired is None:
        return False
    if route is not None and paired is not None:
        raise ValueError("Ambiguous native NPC journey")
    if (
        state.fight is not None
        or getattr(state, "combat_session", None) is not None
        or state.spectator_session is not None
    ):
        raise ValueError("NPC travel requires an idle owned scene")

    def transition(allowed_accounts):
        def entry(db, store, character, proof):
            target = owned_story_npc_entry.route_target_map(db, proof["route_key"])

            def initialize(entry_db, owned_session):
                dungeon_runtime.initialize_instance(
                    entry_db,
                    owned_session,
                    groups=runtime.COMBAT_GROUPS,
                    geometry=map_geometry(target),
                    store=store,
                )

            return owned_story_npc_entry.enter_choice(
                db,
                store,
                character,
                proof,
                initialize_instance=initialize,
                resolve_destination=dungeon_runtime.entry_destination,
                allowed_position_accounts=allowed_accounts,
            )

        return quest_npc.choose(
            runtime.STORE,
            state.account_id,
            state.generation,
            state.character,
            session,
            state.body,
            choice_entry=entry,
            paired_position_accounts=allowed_accounts if paired is not None else None,
        )

    outcome = dungeon_position_barrier.run_party_entry(
        runtime.STORE,
        runtime.POSITIONS,
        state.account_id,
        state.character["id"],
        transition=transition,
    )
    if paired is None and "owned_entry" not in outcome:
        raise ValueError("Accepted NPC travel did not create its owned destination")
    # The position fence has already rebound the durable destination. Publishing
    # the old scene through the quest-state merge would overwrite that baseline;
    # the ordinary outbox bootstrap below hydrates all committed reward state.
    runtime.send_batch(state.connection, state.service, outcome["packets"])
    public = (
        outcome.get("saved")
        if paired is not None
        else outcome["owned_entry"].get("public_arrival")
    )
    if paired is not None and public is None:
        raise ValueError(
            "Accepted paired NPC journey did not commit its public destination"
        )
    if public is not None:
        from wakfu_server import rift_transition_delivery

        rift_transition_delivery.queue_owned_position_refresh(
            state.account_id, state.generation, state.character["id"], public
        )
        app.deliver_rift_transition()
    else:
        app.deliver_dungeon_transitions(before_action=True)
    return True
