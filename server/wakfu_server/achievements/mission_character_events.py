"""Trusted character lifecycle producer for finite reviewed intro activations.

No quest is inferred from visibility or level alone. Only published indexed
character_ready declarations participate, with native eligibility and explicit
reviewed minimum-level evidence. Callers own normal account/character custody.
"""

from contextvars import ContextVar

from . import mission_toolkit

_ACTIVE = ContextVar("reviewed_character_intro_producers", default=frozenset())


def _current(db, store, character):
    current = store.character(character["account_id"], character["id"], db)
    if current is None or (current["id"], current["account_id"]) != (
        character["id"],
        character["account_id"],
    ):
        raise ValueError("Character lifecycle producer lost its persisted owner")
    if type(current["level"]) is not int or current["level"] <= 0:
        raise ValueError("Character lifecycle producer needs its real persisted level")
    return current


def _emit(db, store, character, token):
    identity = character["id"]
    if identity in _ACTIVE.get():
        return []
    guard = _ACTIVE.set(_ACTIVE.get() | {identity})
    try:
        packets = []
        current = _current(db, store, character)
        while True:
            observed = current["level"]
            packets.extend(
                mission_toolkit.settle(
                    db,
                    store,
                    current,
                    f"{token}:level:{observed}",
                    "character_ready",
                    0,
                )
            )
            # Settlement may drain other already-earned rewards. Observe their
            # final level after their outbox rows are delivered, without nested
            # settlement of the currently executing entitlement.
            current = _current(db, store, current)
            if current["level"] <= observed:
                return packets
    finally:
        _ACTIVE.reset(guard)


def level_changed(db, store, character, previous_level):
    """Consume an actual mutation after durable XP/level reconciliation."""
    if type(previous_level) is not int or previous_level <= 0:
        raise ValueError("Missing prior real character level")
    current = _current(db, store, character)
    if current["level"] <= previous_level:
        return []
    return _emit(db, store, current, f"real-level:{previous_level}:{current['level']}")


def after_combat(db, store, character, fight_id):
    """Normal settlement supplies an actual durable fight-reward level origin."""
    row = db.execute(
        "SELECT start_level FROM fight_rewards WHERE fight_id=%s AND character_id=%s AND account_id=%s",
        (fight_id, character["id"], character["account_id"]),
    ).fetchone()
    return (
        [] if row is None else level_changed(db, store, character, row["start_level"])
    )


def ready(store, account_id, generation, character):
    """Post-bootstrap readiness authenticates the actual selected character."""
    from wakfu_server.paid_containers import _leased_owner

    with store.connection() as db:
        _leased_owner(store, db, account_id, generation, character)
        current = _current(db, store, character)
        return _emit(
            db,
            store,
            current,
            f"selected-ready:{generation}:{current['map_id']}:{current.get('instance_id', 0)}",
        )
