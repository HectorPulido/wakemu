"""Narrow session bridge for the original mercenary board UI protocol."""
from .dispatch_result import DispatchResult


def dispatch(session):
    """Return None for other packets; caller supplies the existing loaded gate."""
    from psycopg import Error as DatabaseError
    from psycopg_pool import PoolTimeout
    from wakfu_server import mercenary_boards
    from wakfu_server.ecology_feedback import information

    state, runtime = session.state, session.runtime
    selecting = state.opcode == 12864
    if not selecting and not (
        state.opcode == 12870 and mercenary_boards.recognizes(state.body)
    ):
        return None
    offer = getattr(state, "mercenary_board_offer", None)
    state.mercenary_board_offer = None
    try:
        if session.environment_blocked() or state.environment_ticket is not None:
            raise ValueError("Mercenary board interaction is unavailable now")
        with runtime.POSITIONS.account_barrier(state.account_id):
            runtime.flush_positions(account_id=state.account_id)
            if selecting:
                packets = mercenary_boards.select(
                    runtime.STORE,
                    state.account_id,
                    state.generation,
                    state.character,
                    offer,
                    state.body,
                )
            else:
                state.mercenary_board_offer = mercenary_boards.open_board(
                    runtime.STORE,
                    state.account_id,
                    state.generation,
                    state.character,
                    state.body,
                )
                if state.mercenary_board_offer is None:
                    raise ValueError(
                        "Mercenary board has no published playable contracts"
                    )
                packets = []  # Native bEY already opened the UI locally.
        session.publish_settled_quest_packets(packets)
        runtime.record(
            event="native_mercenary_selection"
            if selecting
            else "native_mercenary_offer",
            actor_id=state.character["id"],
            packets=len(packets),
        )
    except (ValueError, DatabaseError, PoolTimeout) as error:
        runtime.record(
            event="native_mercenary_rejected",
            actor_id=state.character["id"],
            reason=str(error)
            if isinstance(error, ValueError)
            else type(error).__name__,
        )
        runtime.send(
            state.connection,
            state.service,
            *information(
                "This contract is unavailable. Reopen the mercenary board "
                "and choose an available contract."
            ),
        )
    return DispatchResult.CONTINUE
