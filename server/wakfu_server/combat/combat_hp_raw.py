"""HP fff.fZB raw-current authority from actual fresh constructor operands."""
from .combat_casting_range import int32

SOURCE = "fresh_initial_tB_HP.on_resource_override"


def install_fresh_hp_operand(actor, record):
    if (
        not isinstance(record, dict)
        or record.get("producer") != SOURCE
        or record.get("actor_id") != actor.id
        or type(record.get("raw_current")) is not int
        or not -(1 << 31) <= record["raw_current"] < (1 << 31)
        or 1 in actor.effect_frozen
    ):
        raise ValueError("Missing actual fresh constructor HP.on operand")
    from .combat_character_copy_metadata import native_copy_characteristics

    high = native_copy_characteristics()["fresh_characteristics"]["1"]["hard_maximum"]
    raw = max(actor.effect_minima[1], min(high, record["raw_current"]))
    effective = max(actor.effect_minima[1], min(actor.effect_maxima[1], raw))
    if actor.hp != effective or actor.effect_stats[1] != effective:
        raise ValueError("Fresh HP.on operand disagrees with effective actor")
    actor.effect_hp_raw_current = raw
    actor.native_hp_raw_current_source = SOURCE
    actor.native_hp_on_operand = dict(record)


def hp_raw_present(actor):
    return (
        getattr(actor, "native_copy_pa_source", None) is not None
        or getattr(actor, "native_hp_raw_current_source", None) is not None
    )


def hp_raw_current(actor):
    if getattr(actor, "native_copy_pa_source", None) is not None:
        from .combat_copied_pa import copied_raw_current

        return copied_raw_current(actor, 1)
    raw = getattr(actor, "effect_hp_raw_current", None)
    if (
        getattr(actor, "native_hp_raw_current_source", None) != SOURCE
        or type(raw) is not int
        or not -(1 << 31) <= raw < (1 << 31)
        or actor.hp != actor.effect_stats[1]
        or actor.hp != max(actor.effect_minima[1], min(actor.effect_maxima[1], raw))
    ):
        raise ValueError("Missing actual HP raw/effective current authority")
    return raw


def hp_shift_result(actor, amount, *, subtract=False):
    raw = hp_raw_current(actor)
    current, maximum, minimum = actor.hp, actor.effect_maxima[1], actor.effect_minima[1]
    if 1 in actor.effect_frozen:
        return raw, current, 0
    requested = (
        (minimum if amount > current - minimum else int32(raw - amount))
        if subtract
        else (maximum if amount > maximum - current else int32(raw + amount))
    )
    from .combat_character_copy_metadata import native_copy_characteristics

    definition = native_copy_characteristics()["fresh_characteristics"]["1"]
    if definition["over_max_current"] is not True:
        raise ValueError("Missing original HP fZB proof")
    after = max(minimum, min(definition["hard_maximum"], requested))
    effective = max(minimum, min(maximum, after))
    return after, effective, int32(raw - after if subtract else after - raw)


def set_hp_raw_current(actor, requested):
    hp_raw_current(actor)
    if 1 in actor.effect_frozen:
        return
    from .combat_character_copy_metadata import native_copy_characteristics

    high = native_copy_characteristics()["fresh_characteristics"]["1"]["hard_maximum"]
    raw = max(actor.effect_minima[1], min(high, int32(requested)))
    if getattr(actor, "native_copy_pa_source", None) is not None:
        actor.effect_characteristic_raw_currents[1] = raw
    else:
        actor.effect_hp_raw_current = raw
    actor.hp = actor.effect_stats[1] = max(
        actor.effect_minima[1], min(actor.effect_maxima[1], raw)
    )


def shift_hp_raw_current(actor, amount, *, subtract=False):
    raw, _, actual = hp_shift_result(actor, amount, subtract=subtract)
    set_hp_raw_current(actor, raw)
    return actual


def set_hp_raw_maximum(actor, requested):
    """fff.or leaves fZB HP raw current unchanged, including frozen pools."""
    from .combat_maximum_resource import _snapshot, effective_maximum

    _, _, _, minimum, raw_min, percent, low, high = _snapshot(actor, 1)
    raw_current = hp_raw_current(actor)
    raw_maximum = max(raw_min, int32(requested))
    maximum = effective_maximum(raw_maximum, percent, low, high)
    actor.effect_base_maxima[1] = raw_maximum
    actor.max_hp = actor.effect_maxima[1] = maximum
    actor.hp = actor.effect_stats[1] = max(minimum, min(maximum, raw_current))


def set_hp_raw_minimum(actor, requested):
    from .combat_maximum_resource import _snapshot

    _, raw_maximum, maximum, _, _, _, low, high = _snapshot(actor, 1)
    raw = hp_raw_current(actor)
    raw_minimum = min(raw_maximum, int32(requested))
    minimum = max(low, min(high, raw_minimum))
    if 1 not in actor.effect_frozen:
        raw = max(raw, minimum)
    actor.effect_base_minima[1] = raw_minimum
    actor.effect_minima[1] = minimum
    if getattr(actor, "native_copy_pa_source", None) is not None:
        actor.effect_characteristic_raw_currents[1] = raw
    else:
        actor.effect_hp_raw_current = raw
    actor.hp = actor.effect_stats[1] = max(minimum, min(maximum, raw))


def set_hp_raw_percentage(actor, percentage):
    """fff.om/Ub changes sfV without rewriting its raw current."""
    from .combat_maximum_resource import _snapshot, effective_maximum

    _, raw_maximum, _, minimum, _, _, low, high = _snapshot(actor, 1)
    raw_current = hp_raw_current(actor)
    actor.effect_percentages[1] = int32(percentage)
    maximum = effective_maximum(raw_maximum, actor.effect_percentages[1], low, high)
    actor.max_hp = actor.effect_maxima[1] = maximum
    actor.hp = actor.effect_stats[1] = max(minimum, min(maximum, raw_current))
