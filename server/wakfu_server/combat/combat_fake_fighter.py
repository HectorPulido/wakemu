"""Proven faW constructor population without invented fighter resources."""
import math
import struct


def _float32(value):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError("Missing finite native faW constructor parameter")
    try:
        return struct.unpack(">f", struct.pack(">f", value))[0]
    except (OverflowError, struct.error) as error:
        raise ValueError("Invalid native faW float parameter") from error


def _int(value):
    return max(-(1 << 31), min((1 << 31) - 1, math.trunc(value)))


def fake_fighter_constructor(definition):
    if (
        definition.get("type") != "FAKE_FIGHTER"
        or definition.get("native_type_id") != 15
        or definition.get("native_class") != "bcQ"
    ):
        raise ValueError("Missing native faW prototype contract")
    raw = definition.get("raw_bdh")
    if not isinstance(raw, (tuple, list)) or len(raw) < 10:
        raise ValueError("Missing native faW constructor parameters")
    p = tuple(_float32(value) for value in raw)
    # These branches create actual PA records, with defaults and owner-copy
    # flags. Until those producers exist, preserve their absence explicitly.
    if p[1] != -1 or 0 <= p[9] <= 127 or len(p) >= 14:
        raise ValueError("Native faW characteristic constructor authority unavailable")
    height = _int(p[8])
    return dict(
        kind=max(-(1 << 31), min((1 << 31) - 1, math.floor(p[0] + 0.5))),
        movement_blocking=p[3] == 1,
        visibility_obstacle=p[4] == 1,
        obstacle=p[3] == 1 or p[4] == 1,
        running_effect_manager=p[5] == 1,
        owner_activation=p[6] == 1,
        other_activation=p[7] == 1,
        height=((height + 128) % 256) - 128 if height > 0 else 6,
        # faW itself has no additional characteristic container on this path.
        characteristic_ids=(),
    )


def verified_fake_fighter(row, definition):
    expected = fake_fighter_constructor(definition)
    if row.get("native_faw_constructor") != expected:
        raise ValueError("Missing native faW constructor snapshot")
    if expected["kind"] == 4:
        from .combat_microbot_network import SOURCE

        if row.get("native_microbot_network_source") != SOURCE:
            raise ValueError("Missing native faW microbot registration authority")
    slot = row.get("native_obstacle_id")
    source = row.get("native_obstacle_source")
    if expected["obstacle"]:
        if not (
            (type(slot) is int and 0 <= slot <= 126 and source == "QI.f(QK)")
            or (slot == -1 and source == "QI.g(QK)")
        ):
            raise ValueError("Missing native faW QI registration authority")
    elif slot != -1 or source != "fbm.constructor":
        raise ValueError("Invalid native non-obstacle faW identity")
    return expected
