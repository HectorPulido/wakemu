"""Publish authenticated interaction outcomes through the shared quest refresh."""


def settle_interaction(session, handler, *, event, object_id):
    """Run one producer with the session's owner fence and committed position.

    The producer owns its SQL transaction and source validation. All incremental
    inventory and quest packets stay owner-scoped, after reward state refresh.
    """
    state, runtime = session.state, session.runtime
    with runtime.POSITIONS.account_barrier(state.account_id):
        runtime.flush_positions(
            account_id=state.account_id,
            generation=state.generation,
            character_id=state.character["id"],
        )
        result = handler(
            runtime.STORE,
            state.account_id,
            state.generation,
            state.character,
            state.body,
            loaded=state.loaded,
            blocked=session.environment_blocked()
            or state.environment_ticket is not None,
        )
        if not result["applied"] and not result.get("handled"):
            return False
        state.character = result["character"]
        session.publish_settled_quest_packets(result["packets"])
        runtime.record(
            event=event,
            actor_id=state.character["id"],
            object_id=object_id,
            completed=result["completed"],
        )
    return True
