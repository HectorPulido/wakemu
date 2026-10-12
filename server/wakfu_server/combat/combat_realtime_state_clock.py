"""Native eZV realtime deadlines and state310 combat expiry suppression.

A deadline does not imply state removal: eZV.b(aAa) deliberately keeps a
state whose current PN is eVw. Other contexts call the existing removal path.
Rows are plain checkpoint data; clock readings/callbacks are never persisted.
"""


def _integer(value, name, *, positive=False):
    if type(value) is not int or not -(1 << 63) <= value < (1 << 63):
        raise ValueError(f"Missing native realtime {name}")
    if positive and value <= 0:
        raise ValueError(f"Positive native realtime {name} required")
    return value


def register_realtime_state(clocks, *, uid, duration_ms, now_ms, in_combat):
    """eZV.p stores wall-clock now+remaining; fresh eZk uses fyW.guH."""
    _integer(uid, "UID", positive=True)
    _integer(duration_ms, "duration", positive=True)
    _integer(now_ms, "clock")
    if not isinstance(clocks, dict) or type(in_combat) is not bool:
        raise ValueError("Owned native realtime registry/context required")
    if uid in clocks:
        raise ValueError("Duplicate native realtime state UID")
    deadline = _integer(now_ms + duration_ms, "deadline")
    clocks[uid] = dict(deadline_ms=deadline, in_combat=in_combat)


def migrate_realtime_state(clocks, uid, *, now_ms, in_combat):
    """eZk.h(PN) transfers max(1,remaining); eZV.p schedules the clone."""
    _integer(now_ms, "clock")
    if type(in_combat) is not bool or uid not in clocks:
        raise ValueError("Existing native realtime state/context required")
    row = clocks[uid]
    remaining = max(1, _integer(row["deadline_ms"], "deadline") - now_ms)
    row.update(
        deadline_ms=_integer(now_ms + remaining, "deadline"), in_combat=in_combat
    )


def expire_realtime_states(clocks, *, now_ms, remove):
    """Deliver due aAo callbacks; combat state310 survives without mutation.

    A successful external removal cancels its timer, as eZV.r(Qe) does.
    Failed removals retain their deadline so errors cannot hide a live timer.
    """
    _integer(now_ms, "clock")
    if not isinstance(clocks, dict) or not callable(remove):
        raise ValueError("Owned native realtime registry/removal required")
    removed = []
    for uid, row in tuple(clocks.items()):
        _integer(uid, "UID", positive=True)
        deadline = _integer(row["deadline_ms"], "deadline")
        if type(row["in_combat"]) is not bool:
            raise ValueError("Explicit native realtime context required")
        if deadline > now_ms or row["in_combat"]:
            continue
        remove(uid)
        clocks.pop(uid, None)
        removed.append(uid)
    return tuple(removed)
