"""Safe publication boundary for authenticated post-bootstrap intro events."""


def ready(session):
    from psycopg import Error as DatabaseError
    from psycopg_pool import PoolTimeout
    from wakfu_server.achievements import mission_character_events

    state, runtime = session.state, session.runtime
    if not state.selected or not state.loaded:
        return False
    try:
        with runtime.POSITIONS.account_barrier(state.account_id):
            runtime.flush_positions(
                account_id=state.account_id,
                generation=state.generation,
                character_id=state.character["id"],
            )
            packets = mission_character_events.ready(
                runtime.STORE, state.account_id, state.generation, state.character
            )
        if packets:
            session.publish_settled_quest_packets(packets)
        return True
    except (ValueError, DatabaseError, PoolTimeout) as error:
        runtime.record(
            event="reviewed_character_intro_unavailable",
            actor_id=state.character["id"],
            reason=type(error).__name__,
        )
        return False
