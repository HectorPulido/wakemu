"""Verified native constructor facts for configured fbd wall areas."""

import math
import struct


def _float32(value):
    return struct.unpack(">f", struct.pack(">f", value))[0]


def _java_float_to_int(value):
    if math.isnan(value):
        return 0
    if value <= -(1 << 31):
        return -(1 << 31)
    if value >= (1 << 31) - 1:
        return (1 << 31) - 1
    return int(value)


def wall_constructor(definition, level):
    """Return constructor-derived fbd state after validating its native source.

    fbd.aQc consumes the first four `bhe` values when present: HP base,
    per-level HP, movement blocking and line-of-sight blocking. It creates a
    mandatory Qf manager in that same valid-constructor branch.
    """
    if (
        not isinstance(definition, dict)
        or definition.get("type") != "WALL"
        or definition.get("native_class") != "bcZ"
        or definition.get("native_type_id") != 7
        or definition.get("native_container_type") != 3
    ):
        raise ValueError("Missing native bcZ/fbd wall constructor authority")
    if type(level) is not int or not -32768 <= level <= 32767:
        raise ValueError("Native fbd wall level must be a short")
    raw = definition.get("raw_bdh")
    if not isinstance(raw, (list, tuple)) or len(raw) < 4:
        raise ValueError("Native fbd wall requires four constructor parameters")
    if any(type(value) not in (int, float) for value in raw[:4]):
        raise ValueError("Invalid native fbd wall constructor parameter")

    base, per_level, movement, line_of_sight = (_float32(float(v)) for v in raw[:4])
    hp_delta = _float32(_float32(float(level)) * per_level)
    hp = _java_float_to_int(_float32(base + hp_delta))
    hp_maximum = max(0, hp)
    movement_blocking = movement == 1.0
    los_blocking = line_of_sight == 1.0
    return {
        "hp": hp,
        "hp_maximum": hp_maximum,
        "hp_initial": hp_maximum,
        "hp_base": base,
        "hp_per_level": per_level,
        "hp_source": "fbd.aQc.bhe[0]+cmZ()*bhe[1]",
        "obstacle": movement_blocking or los_blocking,
        "obstacle_source": "fbd.bcO:rMI_or_rMJ",
        "movement_blocking": movement_blocking,
        "movement_source": "fbd.bcP:rMI",
        "los_blocking": los_blocking,
        "los_source": "fbd.fTq:rMJ",
        "mandatory_qf": True,
        "qf_source": "fbd.aQc.bgq_eZV",
        "running_effect_manager": True,
        "running_effect_manager_source": "fbd.aQc.mandatory_qf",
        "qf_callback_channel": 1,
        "qf_callback_channel_source": "Qq.bcx",
        "bcK_value": 6,
        "bcK_source": "fbd.bcK",
        "parameters": (base, per_level, movement, line_of_sight),
    }


def verified_wall_constructor(row, definition):
    """Verify the persisted area checkpoint against its source definition."""
    if (
        not isinstance(row, dict)
        or row.get("native_area_contract") != "fbd"
        or row.get("native_type_id") != 7
        or row.get("native_running_effect_manager") is not True
    ):
        raise ValueError("Missing registered native fbd wall constructor")
    expected = wall_constructor(definition, row.get("level"))
    if row.get("native_wall_constructor") != expected:
        raise ValueError("Native bcZ wall constructor checkpoint mismatch")
    wall_hp_state(row, expected)
    if expected["obstacle"]:
        if (
            type(row.get("native_obstacle_id")) is not int
            or not 0 <= row["native_obstacle_id"] <= 126
            or row.get("native_obstacle_source") != "QI.f(QK)"
        ):
            raise ValueError("Missing registered native bcZ QI obstacle")
    elif (
        row.get("native_obstacle_id") != -1
        or row.get("native_obstacle_source") != "fbm.constructor"
    ):
        raise ValueError("Unexpected native bcZ QI obstacle registration")
    return expected


def wall_hp_state(row, constructor):
    """Read fbd's mutable current HP, separate from immutable constructor data."""
    maximum = constructor.get("hp_maximum")
    current = row.get("native_wall_hp_current") if isinstance(row, dict) else None
    if (
        type(maximum) is not int
        or maximum < 0
        or type(current) is not int
        or row.get("native_wall_hp_source") != "fbd.PA.sgC.aYS"
    ):
        raise ValueError("Missing native fbd current HP authority")
    from .combat_area_hp_pa import area_hp_pa

    return area_hp_pa(
        row,
        dict(
            maximum=maximum,
            minimum=0,
            absolute_minimum=0,
            absolute_maximum=(1 << 31) - 1,
        ),
        current,
        "fbd",
    )


def wall_damage_snapshot(row, definition):
    """Build fbd's present PA stats from its native characteristic universe.

    fbd.aQc initializes the eight rMK characteristics plus HP. The non-HP
    PA values start at zero; HP current/max are the constructor's mutable PA.
    fbd has no actor-only armor, virtual-HP, or barrier characteristics.
    """
    constructor = verified_wall_constructor(row, definition)
    hp = wall_hp_state(row, constructor)
    stats = {
        1: hp["current"],
        17: 0,
        27: 0,
        28: 0,
        29: 0,
        30: 0,
        31: 0,
        49: 0,
        95: 0,
    }
    return {
        "stats": stats,
        "maxima": {1: hp["maximum"]},
        "minima": {1: hp["minimum"]},
        "frozen": frozenset((1,)) if hp["frozen"] else frozenset(),
        "current_hp": hp["current"],
        "maximum_hp": hp["maximum"],
        "characteristics_source": "fbd.aQc.rMK+ffw.sgC/eRF.aYY",
        "mutable_hp_source": hp["source"],
        "zero_characteristics_source": "fbd.rMK+eRF.aYY",
        "absent_actor_absorption_stats": (92, 97, 100),
    }


def update_wall_hp(row, constructor, current):
    """Apply a caller-computed native PA current-value transition."""
    hp = wall_hp_state(row, constructor)
    if type(current) is not int or not hp["minimum"] <= current <= hp["maximum"]:
        raise ValueError("Invalid native fbd current HP update")
    from .combat_area_hp_pa import set_area_hp_current

    set_area_hp_current(row, hp, current, "native_wall_hp_current")
    return wall_hp_state(row, constructor)
