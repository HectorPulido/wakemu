"""Shared native state/effect values; execution and trigger dispatch are separate."""
from .combat_parameters import parameter_value, _float32


def effect_profile(definition, level):
    if type(level) is not int or not -32768 <= level <= 32767:
        raise ValueError("Effect level must be a native signed short")
    return dict(
        parameters=[
            parameter_value(definition["parameters"], index, level)
            for index in range(definition["parameter_count"])
        ],
        probability=_float32(
            _float32(definition["probability_base"])
            + _float32(_float32(definition["probability_per_level"]) * level)
        ),
    )


def state_profile(catalog, reference, requested_level):
    if type(requested_level) is not int or not 0 <= requested_level <= 32767:
        raise ValueError("Invalid native state level")
    definition = catalog["states"].get(str(reference))
    if definition is None:
        raise ValueError("Unknown native state")
    level = min(requested_level, definition["maximum_level"])
    duration = definition["duration_base"] + level * definition["duration_per_level"]
    # fyW.aas uses signed Java int arithmetic.
    duration = (duration + (1 << 31)) % (1 << 32) - (1 << 31)
    realtime = (
        definition["realtime_duration_base"]
        + level * definition["realtime_duration_per_level"]
    )
    realtime = (realtime + (1 << 31)) % (1 << 32) - (1 << 31)
    return dict(
        reference=reference,
        level=level,
        duration=duration,
        clock_actor=definition["clock_actor"],
        tick_at_turn_end=definition["tick_at_turn_end"],
        additive=definition["additive"],
        replace=definition["replace"],
        refresh=definition["refresh"],
        protected=definition["protected"],
        realtime_duration=realtime,
        skip_turn_timer=definition["skip_turn_timer"],
        effects=[
            root
            for root in definition["effect_ids"]
            if catalog["effects"][str(root)]["minimum_level"]
            <= level
            <= catalog["effects"][str(root)]["maximum_level"]
        ],
    )
