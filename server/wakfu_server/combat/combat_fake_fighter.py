"""Proven faW constructor population without invented fighter resources."""
import math
import struct
from functools import lru_cache
from importlib import import_module


@lru_cache(maxsize=4)
def _dependency_module(name):
    """Keep only cycle-safe module bindings; all constructor guards stay live."""
    return import_module("." + name, __package__)


def _float32(value):
    kind = type(value)
    if kind is int:
        # All integers in this interval are exactly representable in binary32.
        if -16777216 <= value <= 16777216:
            return float(value)
    elif kind is float:
        # Return the original zero to retain its IEEE sign bit.
        if value == 0.0 or value == 1.0 or value == -1.0:
            return value
    else:
        raise ValueError("Missing finite native faW constructor parameter")
    if not math.isfinite(value):
        raise ValueError("Missing finite native faW constructor parameter")
    try:
        return struct.unpack(">f", struct.pack(">f", value))[0]
    except (OverflowError, struct.error) as error:
        raise ValueError("Invalid native faW float parameter") from error


def _int(value):
    return max(-(1 << 31), min((1 << 31) - 1, math.trunc(value)))


def fake_fighter_constructor(definition, level=None, *, allow_hp=False):
    return _fake_fighter_constructor_plan(definition, level, allow_hp=allow_hp)[0]


def _fake_fighter_constructor_plan(definition, level=None, *, allow_hp=False):
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
    # Native catalog containers have no user callbacks. Preserve legacy reads
    # for custom mappings/sequences, whose get/iteration may have side effects.
    share_parameters = (
        type(definition) is dict
        and type(raw) in (list, tuple)
        and type(definition.get("type")) is str
        and type(definition.get("native_class")) is str
        and type(definition.get("native_type_id")) is int
    )
    # These branches create actual PA records, with defaults and owner-copy
    # flags. Until those producers exist, preserve their absence explicitly.
    characteristic_ids = ()
    resources = None
    if p[1] != -1 or 0 <= p[9] <= 127 or len(p) >= 14:
        if allow_hp is not True:
            raise ValueError(
                "Native faW characteristic constructor authority unavailable"
            )
        owner_copy = _dependency_module("combat_fake_fighter_owner_copy")
        resource_module = _dependency_module("combat_fake_fighter_resources")
        if share_parameters:
            mask = owner_copy._damage_only_mask_from_parameters(definition, p)
        else:
            mask = owner_copy.damage_only_mask(definition)
        if mask is not None:
            characteristic_ids = (20,)
        else:
            if share_parameters:
                resources = resource_module._owned_resources_from_parameters(
                    definition, level, p
                )
            else:
                resources = resource_module._owned_resources_constructor(
                    definition, level
                )
            characteristic_ids = tuple(resources["characteristics"])
    height = _int(p[8])
    return (
        dict(
            kind=max(-(1 << 31), min((1 << 31) - 1, math.floor(p[0] + 0.5))),
            movement_blocking=p[3] == 1,
            visibility_obstacle=p[4] == 1,
            obstacle=p[3] == 1 or p[4] == 1,
            running_effect_manager=p[5] == 1,
            owner_activation=p[6] == 1,
            other_activation=p[7] == 1,
            height=((height + 128) % 256) - 128 if height > 0 else 6,
            # faW itself has no additional characteristic container on this path.
            characteristic_ids=characteristic_ids,
        ),
        resources,
        p if share_parameters else None,
    )


def verified_fake_fighter(row, definition):
    has_hp = (
        "native_faw_hp_constructor" in row
        or "native_faw_damage_only_constructor" in row
    )
    expected, resources, parameters = _fake_fighter_constructor_plan(
        definition, row.get("level"), allow_hp=has_hp
    )
    if row.get("native_faw_constructor") != expected:
        raise ValueError("Missing native faW constructor snapshot")
    if has_hp:
        _dependency_module("combat_fake_fighter_resources")._characteristics_from_plan(
            row, definition, parameters, resources
        )
    if expected["kind"] == 4:
        if (
            row.get("native_microbot_network_source")
            != _dependency_module("combat_microbot_network").SOURCE
        ):
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
