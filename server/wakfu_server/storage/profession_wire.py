"""Absolute native CRAFT snapshots; never replay XP reward deltas on login."""
import math
import struct

from .inventory_items import _varint


MAX_XP = 3_000_000


def level(xp):
    if type(xp) is not int or not 0 <= xp <= MAX_XP:
        raise ValueError("Invalid cumulative profession XP")
    return math.isqrt(xp // 75)


def _integer(value, maximum):
    if type(value) is not int or not 0 <= value <= maximum:
        raise ValueError("Invalid native craft integer")
    return value


def _number(field, value):
    return _varint(field << 3) + _varint(value)


def _message(field, body):
    return _varint((field << 3) | 2) + _varint(len(body)) + body


def snapshot(professions, *, configuration, additional):
    """Encode du/dh with explicit server-owned settings and additional state.

    Each profession owns cumulative xp, four native counters and learned action
    IDs. configuration is dA; additional is do. Callers must preserve both
    account components instead of silently replacing them with empty messages.
    An initially empty account uses dA=0800 and do=18002000, as the native
    builder does. These bytes must not come from another account's capture.
    """
    if not isinstance(professions, dict) or len(professions) > 128:
        raise ValueError("Invalid profession snapshot")
    if any(
        type(body) is not bytes or len(body) > 1_048_576
        for body in (configuration, additional)
    ):
        raise ValueError("Invalid native craft account components")
    for profession_id in professions:
        _integer(profession_id, 2**31 - 1)
        if profession_id == 0:
            raise ValueError("Invalid profession identity")
    entries = []
    for profession_id in sorted(professions):
        state = professions[profession_id]
        if not isinstance(state, dict) or set(state) != {"xp", "counters", "actions"}:
            raise ValueError("Incomplete profession snapshot")
        level(state["xp"])
        counters = state["counters"]
        actions = state["actions"]
        if (
            not isinstance(counters, (list, tuple))
            or len(counters) != 4
            or not isinstance(actions, (list, tuple))
            or len(actions) > 65536
        ):
            raise ValueError("Invalid native craft state")
        bonuses = b""
        for field, value in enumerate(counters, 1):
            _integer(value, 2**31 - 1)
            if value:
                bonuses += _number(field, value)
        validated_actions = [_integer(value, 2**31 - 1) for value in actions]
        if len(set(validated_actions)) != len(validated_actions):
            raise ValueError("Duplicate learned craft action")
        owned = _number(1, state["xp"]) + _message(2, bonuses)
        for action_id in sorted(validated_actions):
            owned += _message(3, _number(1, action_id))
        entries.append(_message(1, _number(1, profession_id) + _message(2, owned)))
    payload = b"".join(entries) + _message(2, configuration) + _message(3, additional)
    return 13873, struct.pack(">III", 1, 14, len(payload)) + payload
