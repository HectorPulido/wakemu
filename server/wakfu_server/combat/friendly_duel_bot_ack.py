"""Headless duel participant presentation and terminal lifecycle."""
import struct


def bot_session(shared):
    if not getattr(shared, "is_duel", False):
        return None
    context = getattr(shared, "join_context", None) or {}
    identity = context.get("ai_bot_character_id")
    if identity is None:
        return None
    if type(identity) is not int:
        raise ValueError("Invalid friendly bot identity")
    sessions = [
        session
        for session in shared.participants.values()
        if session.character_id == identity
    ]
    if len(sessions) != 1:
        raise ValueError("Missing friendly bot participant")
    return sessions[0]


def acknowledge_delivered(adapter, shared):
    """A headless peer has no presentation to animate or client to ACK it."""
    with shared.lock:
        session = bot_session(shared)
        if session is None or session.account_id in shared.returned:
            return False
        barrier = shared.ack
        if (
            barrier.turn is None
            or barrier.expected.get(session.account_id) != session.generation
            or session.account_id in barrier.received
        ):
            return False
        return adapter.acknowledge(
            session,
            shared.fight.id,
            struct.pack(">i", barrier.turn),
            lambda candidate, runtime, body: runtime.acknowledge_turn(body),
        )


def return_settled(adapter, shared):
    """The bot has no result window from which to request its return."""
    with shared.lock:
        session = bot_session(shared)
        if session is None or not shared.settlement_ready:
            return False
        if session.account_id in shared.returned:
            return False
    return adapter.mark_returned(session, shared.fight.id)
