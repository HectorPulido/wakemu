"""eGj's ffu listener: Breeze maximum = 50 + 75 * WP maximum.

This constructor dependency belongs to every actual ffh carrying both PCs,
independently of breed. It reacts to PA maximum setters, never turn polling.
"""
from .combat_casting_range import int32

SOURCE = "eGj.ffu_WP_sfY_to_Breeze_or"


def install(actor):
    if 4 not in actor.effect_stats or 111 not in actor.effect_stats:
        return
    actor.native_hupper_resource_binding = SOURCE
    actor.native_hupper_resource_raw_current = actor.effect_stats[111]
    maximum_changed(actor, 4)


def maximum_changed(actor, stat):
    if stat != 4 or getattr(actor, "native_hupper_resource_binding", None) != SOURCE:
        return
    from .combat_actor_snapshot import native_actor_catalog
    from .combat_maximum_resource import effective_maximum
    from .combat_character_copy_metadata import native_copy_characteristics

    row = native_actor_catalog()["characteristics"]["111"]
    raw_max = max(
        actor.effect_base_minima[111], int32(50 + int32(75 * actor.effect_maxima[4]))
    )
    maximum = effective_maximum(
        raw_max, actor.effect_percentages[111], row["hard_minimum"], row["hard_maximum"]
    )
    raw = (
        actor.effect_characteristic_raw_currents[111]
        if getattr(actor, "native_copy_pa_source", None) is not None
        else actor.native_hupper_resource_raw_current
    )
    over_max = native_copy_characteristics()["fresh_characteristics"]["111"][
        "over_max_current"
    ]
    if 111 not in actor.effect_frozen and not over_max:
        raw = min(raw, maximum)
    actor.native_hupper_resource_raw_current = raw
    if getattr(actor, "native_copy_pa_source", None) is not None:
        actor.effect_characteristic_raw_currents[111] = raw
    actor.effect_base_maxima[111] = raw_max
    actor.effect_maxima[111] = maximum
    actor.effect_stats[111] = max(actor.effect_minima[111], min(maximum, raw))


def set_current(actor, value):
    """fff.on on the linked PA, retaining expandable hidden raw current."""
    from .combat_actor_snapshot import native_actor_catalog
    from .combat_character_copy_metadata import native_copy_characteristics

    if getattr(actor, "native_hupper_resource_binding", None) != SOURCE:
        return False
    if 111 in actor.effect_frozen:
        return True
    row = native_actor_catalog()["characteristics"]["111"]
    over_max = native_copy_characteristics()["fresh_characteristics"]["111"][
        "over_max_current"
    ]
    upper = row["hard_maximum"] if over_max else actor.effect_maxima[111]
    raw = max(actor.effect_minima[111], min(upper, int32(value)))
    actor.native_hupper_resource_raw_current = raw
    if getattr(actor, "native_copy_pa_source", None) is not None:
        actor.effect_characteristic_raw_currents[111] = raw
    actor.effect_stats[111] = max(
        actor.effect_minima[111], min(actor.effect_maxima[111], raw)
    )
    return True
