"""Owned Tc/SY progress and fem removal snapshots at actual mutations."""


def short(value):
    return (value + 32768) % 65536 - 32768


def initialize(fight, identities):
    fight.native_timeline_member_counters = {
        str(identity): 0 for identity in identities
    }
    fight.native_timeline_removed = []
    fight.native_timeline_snapshot_source = "owned-tc-sy-v1"


def counters(fight):
    result = getattr(fight, "native_timeline_member_counters", None)
    if getattr(
        fight, "native_timeline_snapshot_source", None
    ) != "owned-tc-sy-v1" or not isinstance(result, dict):
        raise ValueError("Missing authoritative native timeline progress snapshot")
    return result


def end_current(fight):
    rows = counters(fight)
    key = str(fight.current.id)
    if key not in rows:
        raise ValueError("Missing native current SY progress")
    rows[key] = short(rows[key] + 1)  # SU end -> Tc.bit -> SY.bif.


def insert(fight, identity, slot):
    rows = counters(fight)
    key = str(identity)
    if key in rows:
        raise ValueError("Duplicate native timeline SY insertion")
    rows[key] = short(fight.native_timeline_round + (slot <= fight.turn_index))


def remove(fight, identity):
    rows = counters(fight)
    key = str(identity)
    if key not in rows:
        return  # NOT_PRESENT_IN_TIMELINE has no Tc/SY or fem removed status.
    index = fight.order.index(identity)
    progress = short(rows.pop(key) + (fight.current.id == identity))
    fight.native_timeline_removed.append(
        dict(actor_id=identity, progress=progress, position=index, modifications=[])
    )
