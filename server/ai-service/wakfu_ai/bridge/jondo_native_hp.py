"""Actual source-bound HP1 bounds and raw authority; missing evidence stays unknown."""


def readonly_hp_projection(actor, *, hp_definition=None):
    """Return actual HP1 bounds/raw authority, or unknown; never infer a state."""
    stats = getattr(actor, "effect_stats", None)
    minima = getattr(actor, "effect_minima", None)
    maxima = getattr(actor, "effect_maxima", None)
    frozen = getattr(actor, "effect_frozen", None)
    hp, maximum = getattr(actor, "hp", None), getattr(actor, "max_hp", None)
    if (
        not all(isinstance(row, dict) for row in (stats, minima, maxima))
        or not isinstance(frozen, (set, frozenset, tuple, list))
        or any(type(stat) is not int for stat in frozen)
        or any(type(row.get(1)) is not int for row in (stats, minima, maxima))
        or type(hp) is not int
        or type(maximum) is not int
        or hp != stats[1]
        or maximum != maxima[1]
        or not 0 <= minima[1] <= hp <= maximum
    ):
        return None
    from wakfu_server.combat_hp_raw import hp_raw_present, hp_raw_current

    result = dict(
        version=1,
        minimum=minima[1],
        frozen=1 in frozen,
        rawCurrentMode="bounded",
        rawCurrent=None,
    )
    if hp_raw_present(actor):
        try:
            raw = hp_raw_current(actor)
        except (ValueError, KeyError, AttributeError):
            return None  # A claimed but invalid raw source is not bounded mode.
        result.update(
            rawCurrent=raw,
            rawCurrentMode=(
                "copied"
                if getattr(actor, "native_copy_pa_source", None) is not None
                else "fresh"
            ),
        )
    if hp_definition is not None:
        if (
            not isinstance(hp_definition, dict)
            or hp_definition.get("over_max_current") is not True
            or type(hp_definition.get("hard_maximum")) is not int
            or hp_definition["hard_maximum"] < maximum
        ):
            return None
        result["hardMaximum"] = hp_definition["hard_maximum"]
    return result


def readonly_healing_projection(actor, *, metadata=None, world_properties=None):
    """Reuse current condition authority; never query it or infer actor type."""
    frozen = getattr(actor, "effect_frozen", None)
    if not isinstance(frozen, (set, frozenset, tuple, list)) or any(
        type(stat) is not int for stat in frozen
    ):
        return {}
    result = dict(nativeVirtualHpFrozen=92 in frozen)
    carried = getattr(metadata, "is_carried", None)
    if type(carried) is bool:
        result["nativeIsCarried"] = carried
    native_type = getattr(metadata, "native_actor_type", None)
    stats, minima, maxima = (
        getattr(actor, name, None)
        for name in ("effect_stats", "effect_minima", "effect_maxima")
    )
    for statistic, name in (
        (97, "nativeArmor"),
        (100, "nativeBarrier"),
        (92, "nativeVirtualHp"),
    ):
        if (
            all(
                isinstance(row, dict) and type(row.get(statistic)) is int
                for row in (stats, minima, maxima)
            )
            and minima[statistic] <= stats[statistic] <= maxima[statistic]
        ):
            result[name] = dict(
                version=1,
                minimum=minima[statistic],
                maximum=maxima[statistic],
                frozen=statistic in frozen,
            )
    if (
        type(native_type) is not int
        or not isinstance(world_properties, (set, frozenset))
        or any(type(value) is not int for value in world_properties)
        or not all(
            isinstance(row, dict) and type(row.get(32)) is int
            for row in (stats, minima, maxima)
        )
        or not minima[32] <= stats[32] <= maxima[32]
    ):
        return result
    enabled = native_type in (0, 5) or 122 in world_properties
    result.update(
        nativeHealingResistanceEnabled=enabled,
        nativeHealingResistance=dict(
            version=1,
            enabled=enabled,
            minimum=minima[32],
            maximum=maxima[32],
            frozen=32 in frozen,
        ),
    )
    return result
