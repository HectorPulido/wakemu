"""Authentic native emote occupations, never synthetic dialogue progress."""

from . import mission_toolkit


def performed(db, store, character, emote_id, operation_id):
    """Called after native authorization under the selected owner's SQL lock.

    The session flushes accepted movement before authorization. This equality
    also protects direct callers against stale location or another character.
    Only published, explicit bindings can consume the resulting event.
    """
    if (
        type(emote_id) is not int
        or emote_id <= 0
        or not isinstance(operation_id, str)
        or len(operation_id) != 32
        or any(c not in "0123456789abcdef" for c in operation_id)
    ):
        raise ValueError("Invalid authenticated native emote identity")
    current = store.character(character["account_id"], character["id"], db)
    if current is None or any(
        current.get(key) != character.get(key)
        for key in ("account_id", "id", "map_id", "instance_id", "x", "y", "z")
    ):
        raise ValueError("Native emote mission fact lost its owned position")
    return mission_toolkit.settle(
        db,
        store,
        current,
        f"native-emote:{operation_id}",
        "emote_performed",
        emote_id,
    )
