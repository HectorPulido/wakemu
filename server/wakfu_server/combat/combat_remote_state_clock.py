"""Pure eZU remaining-time projection from the actual owned state310 clock."""
from .combat_state_ledger import RunningState
from .combat_realtime_state_clock import _integer


def state_remaining_milliseconds(fight, actor_id, uid, duration, now_ms):
    _integer(now_ms, "snapshot clock")
    actor = fight.actors.get(actor_id)
    if actor is None:
        raise ValueError("Missing owned realtime state actor")
    ledger = getattr(actor, "state_ledger", None)
    entries = () if ledger is None else ledger.entries
    matches = tuple(row for row in entries if row.uid == uid)
    if len(matches) != 1 or not isinstance(matches[0], RunningState):
        raise ValueError("Missing unique owned realtime state310 carrier")
    row = matches[0]
    if (
        row.target_id != actor_id
        or row.realtime_duration != duration
        or row.realtime_duration <= 0
        or row.timer is not None
        or row.realtime_in_combat is not True
    ):
        raise ValueError("Unverified owned realtime state310 clock context")
    deadline = _integer(row.realtime_deadline_ms, "state deadline")
    remaining = max(0, deadline - now_ms)
    return ((remaining + (1 << 31)) % (1 << 32)) - (1 << 31)
