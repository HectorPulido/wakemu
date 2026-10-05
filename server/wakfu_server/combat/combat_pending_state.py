"""Native eZk carrier executes its iterator before Qe.d registers it in Qf.

Only a newly applied, retained, owned ledger entry and its own emitted payload
can enter this scope. Unknown missing effects remain missing authority.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from .combat_state_ledger import RunningState

_PENDING = ContextVar("native_pending_state_registration", default=())


def pending_state_uids(fight):
    return frozenset(uid for owner, uid in _PENDING.get() if owner is fight)


@contextmanager
def pending_state_registration(fight, entry):
    if not isinstance(entry, RunningState):
        raise ValueError("Missing native pending state creation authority")
    if not entry.retained:
        yield
        return
    from .combat_state_managers import state_manager

    actor = state_manager(fight, entry.target_id)
    if (
        actor is None
        or not any(value is entry for value in actor.state_ledger.entries)
        or entry.uid not in fight.state_wire_payloads
        or entry.uid in fight.native_retained_records
    ):
        raise ValueError("Unverified new native pending state carrier")
    token = _PENDING.set((*_PENDING.get(), (fight, entry.uid)))
    try:
        yield
    finally:
        _PENDING.reset(token)
