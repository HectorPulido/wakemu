"""Eligibility for idempotent settlement retries on a live owner heartbeat."""


def pending_terminal_settlement(shared):
    if shared is None or getattr(shared, "settlement_ready", False):
        return False
    fight = shared.fight
    if fight.phase != "finished" or fight.winner not in (0, 1):
        return False
    # Explicit surrender has its own durable no-reward cleanup/ACK lifecycle.
    if getattr(shared.runtime, "abandon_owner", None) is not None:
        return False
    return getattr(shared.runtime, "awaiting_ack", None) is None
