"""Native resource metadata and ordered maximum/current equipment projection."""
from functools import lru_cache

from .equipment_resource_projection import apply_operation

STATS = frozenset((2, 3, 4))
REDUCTIONS = {56: 2, 57: 3, 192: 4}


def reduction(effect):
    values = effect.get("values")
    if (
        effect.get("generic") not in REDUCTIONS
        or effect.get("runner") != "eWO"
        or effect.get("parameter_count") != 1
        or not isinstance(values, list)
        or len(values) != 1
        or type(values[0]) is not int
        or not 0 <= values[0] < (1 << 31)
        or effect.get("effect_criteria") is not False
        or effect.get("has_triggers") is not False
        or type(effect.get("target_mask")) is not int
        or effect["target_mask"] != 0
        or type(effect.get("native_variant")) is not int
        or effect["native_variant"] != 0
        or effect.get("native_active_effect") is not False
    ):
        return None
    return REDUCTIONS[effect["generic"]], values[0]


@lru_cache(maxsize=None)
def _flags(reference, effect_id):
    from wakfu_server.combat_character_copy_equipment import (
        native_copied_equipment_catalog,
    )

    definition = native_copied_equipment_catalog()["definitions"][str(reference)]
    pending = list(definition["ordered_effects"])
    root = None
    while pending:
        candidate = pending.pop()
        if candidate["reference"] == effect_id:
            root = candidate
            break
        pending.extend(candidate.get("child_definitions", ()))
    if root is None:
        raise ValueError("Missing original resource equipment root")
    flags = root["metadata"]["native_effect_flags"]
    if not isinstance(flags, (list, tuple)) or any(
        type(flag) is not int for flag in flags
    ):
        raise ValueError("Missing native resource effect flags")
    return tuple(flags)


def kind(reference, effect, stat):
    if stat not in STATS:
        return None
    if reduction(effect) is not None:
        return dict(family="eWO", stat=stat, restore_current=True, reduce_current=True)
    if effect.get("runner") != "eWN" or effect.get("values", [])[1:] != [1, 0]:
        raise ValueError("Unqualified resource equipment operation")
    cap = None if 17 in _flags(reference, effect["id"]) else {2: 16, 3: 8}.get(stat)
    return dict(
        family="eWN", stat=stat, apply_current=True, remove_current=False, cap=cap
    )


def from_native_values(values):
    from wakfu_server.combat_actor_snapshot import native_actor_catalog

    native = native_actor_catalog()["characteristics"]
    rows = {}
    for stat in STATS:
        row = values[stat] if stat in values else values[str(stat)]
        if row.get("frozen") is not False:
            raise ValueError(
                "Frozen resource equipment projection requires its native contract"
            )
        rows[stat] = dict(
            current=row["current"],
            raw_minimum=row["minimum"],
            raw_maximum=row["maximum"],
            percentage=0,
            minimum=row["minimum"],
            maximum=row["maximum"],
            hard_minimum=native[str(stat)]["hard_minimum"],
            hard_maximum=native[str(stat)]["hard_maximum"],
        )
    return rows


def baseline(character, criterion_context=None):
    if (
        criterion_context is not None
        and criterion_context.get("actor_kind") == "native_companion_npc"
    ):
        rows = criterion_context.get("resource_baseline")
        if not isinstance(rows, dict):
            return None
        return rows
    from wakfu_server.breed_resources import base_resources
    from wakfu_server.combat_actor_snapshot import native_actor_catalog

    native = native_actor_catalog()["characteristics"]
    resources = base_resources(character)
    values = {}
    for stat, name in ((2, "AP"), (3, "MP"), (4, "WP")):
        row = native[str(stat)]
        values[stat] = dict(row, current=resources[name], maximum=resources[name])
    return from_native_values(values)


def apply(state, amount, subtract, descriptor):
    descriptor = dict(descriptor)
    if descriptor["family"] == "eWN" and descriptor.get("cap") is not None:
        # Original eWN uses signed cap-minus-RAW even when already over cap.
        from wakfu_server.combat_maximum_resource import _int32

        signed = -amount if subtract else amount
        signed = min(signed, _int32(descriptor["cap"] - state["raw_maximum"]))
        amount, subtract = signed, False
    return apply_operation(state, amount, descriptor, subtract=subtract)


def project(operations, kinds, rows):
    if rows is None:
        if kinds:
            raise ValueError("Missing native companion resource maximum snapshot")
        return dict(initial={}, final={}, steps=[])
    from .equipment_resource_projection import _validated_state

    initial = {stat: _validated_state(row) for stat, row in rows.items()}
    current = {stat: dict(row) for stat, row in initial.items()}
    steps = []
    for index, (stat, amount, subtract) in enumerate(operations):
        if stat not in STATS:
            continue
        descriptor = kinds[index]
        current[stat], receipt = apply(current[stat], amount, subtract, descriptor)
        steps.append(dict(index=index, stat=stat, receipt=receipt))
    return dict(initial=initial, final=current, steps=steps)
