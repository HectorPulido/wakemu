"""Actual PA notifications consumed by native eWq/eWr AP-to-MP listeners.

Call after a proved PA setter, never from a turn or dictionary observer. The
plain listener population survives preview cloning and checkpointing.
"""

SOURCE = "eWq.c_AP.a_eWr_fff.aZk"
RAW_SOURCE = "fresh_ffh_AP_MP_mutable_on_within_bounds"


def resource_raw_current(actor, stat):
    raw = getattr(actor, "effect_resource_raw_currents", None)
    if (
        getattr(actor, "native_resource_raw_current_source", None) != RAW_SOURCE
        or not isinstance(raw, dict)
        or type(raw.get(stat)) is not int
        or not -(1 << 31) <= raw[stat] < (1 << 31)
    ):
        raise ValueError("Missing native PA.aYT raw-current authority")
    return raw[stat]


def set_resource_current(fight, actor, stat, requested):
    """Exact fff.on: expandable PCs clamp raw current to hard upper."""
    from .combat_maximum_resource import _snapshot
    from .combat_actor_snapshot import native_actor_catalog

    current, _, maximum, minimum, *_ = _snapshot(actor, stat)
    resource_raw_current(actor, stat)
    if stat in actor.effect_frozen:
        return
    row = native_actor_catalog()["characteristics"][str(stat)]
    from .combat_character_copy_metadata import native_copy_characteristics

    over_max = native_copy_characteristics()["fresh_characteristics"][str(stat)][
        "over_max_current"
    ]
    upper = row["hard_maximum"] if over_max else maximum
    raw = max(minimum, min(upper, int32(requested)))
    actor.effect_resource_raw_currents[stat] = raw
    if getattr(actor, "native_copy_pa_source", None) is not None:
        actor.effect_characteristic_raw_currents[stat] = raw
    effective = max(minimum, min(maximum, raw))
    actor.effect_stats[stat] = effective
    setattr(actor, {2: "ap", 3: "mp"}[stat], effective)
    notify_resource_pa(fight, actor, stat, before_current=current)


def shift_resource_current(fight, actor, stat, amount, *, subtract=False):
    """Exact fff.nG/oo, including hidden expandable raw current."""
    from .combat_maximum_resource import _snapshot

    raw, _, _ = resource_shift_result(actor, stat, amount, subtract=subtract)
    set_resource_current(fight, actor, stat, raw)


def resource_shift_result(actor, stat, amount, *, subtract=False):
    from .combat_maximum_resource import _snapshot
    from .combat_actor_snapshot import native_actor_catalog

    current, _, maximum, minimum, *_ = _snapshot(actor, stat)
    raw = resource_raw_current(actor, stat)
    if stat in actor.effect_frozen:
        return raw, current, 0
    if subtract:
        requested = minimum if amount > current - minimum else int32(raw - amount)
    else:
        requested = maximum if amount > maximum - current else int32(raw + amount)
    row = native_actor_catalog()["characteristics"][str(stat)]
    from .combat_character_copy_metadata import native_copy_characteristics

    over_max = native_copy_characteristics()["fresh_characteristics"][str(stat)][
        "over_max_current"
    ]
    upper = row["hard_maximum"] if over_max else maximum
    result = max(minimum, min(upper, requested))
    effective = max(minimum, min(maximum, result))
    actual = int32(raw - result if subtract else result - raw)
    return result, effective, actual


def set_resource_maximum(fight, actor, stat, requested):
    """Exact fff.or: frozen/expandable raw current survives maximum changes."""
    from .combat_maximum_resource import _snapshot, effective_maximum
    from .combat_actor_snapshot import native_actor_catalog

    _, _, _, minimum, raw_min, percent, low, high = _snapshot(actor, stat)
    raw_current = resource_raw_current(actor, stat)
    raw_maximum = max(raw_min, int32(requested))
    maximum = effective_maximum(raw_maximum, percent, low, high)
    row = native_actor_catalog()["characteristics"][str(stat)]
    from .combat_character_copy_metadata import native_copy_characteristics

    over_max = native_copy_characteristics()["fresh_characteristics"][str(stat)][
        "over_max_current"
    ]
    if stat not in actor.effect_frozen and not over_max:
        raw_current = min(raw_current, maximum)
    actor.effect_resource_raw_currents[stat] = raw_current
    if getattr(actor, "native_copy_pa_source", None) is not None:
        actor.effect_characteristic_raw_currents[stat] = raw_current
    actor.effect_base_maxima[stat] = raw_maximum
    actor.effect_maxima[stat] = maximum
    actor.effect_stats[stat] = max(minimum, min(maximum, raw_current))
    setattr(actor, {2: "max_ap", 3: "max_mp"}[stat], maximum)
    setattr(actor, {2: "ap", 3: "mp"}[stat], actor.effect_stats[stat])
    notify_resource_pa(fight, actor, stat, maximum=True)


def set_resource_minimum(fight, actor, stat, requested):
    """Exact fff.os: preserve frozen raw current and always notify."""
    from .combat_maximum_resource import _snapshot

    _, raw_maximum, maximum, _, _, _, low, high = _snapshot(actor, stat)
    raw_current = resource_raw_current(actor, stat)
    raw_minimum = min(raw_maximum, int32(requested))
    minimum = max(low, min(high, raw_minimum))
    if stat not in actor.effect_frozen:
        raw_current = max(raw_current, minimum)
    actor.effect_resource_raw_currents[stat] = raw_current
    if getattr(actor, "native_copy_pa_source", None) is not None:
        actor.effect_characteristic_raw_currents[stat] = raw_current
    actor.effect_base_minima[stat] = raw_minimum
    actor.effect_minima[stat] = minimum
    actor.effect_stats[stat] = max(minimum, min(maximum, raw_current))
    setattr(actor, {2: "ap", 3: "mp"}[stat], actor.effect_stats[stat])
    notify_resource_pa(fight, actor, stat, maximum=True)


def int32(value):
    return (value + (1 << 31)) % (1 << 32) - (1 << 31)


def _listeners(fight, actor):
    population = getattr(fight, "native_resource_pa_listeners", {})
    if not isinstance(population, dict):
        raise ValueError("Invalid actual native PA listener population")
    rows = population.get(actor.id, [])
    if not isinstance(rows, list):
        raise ValueError("Invalid actual native PA listener order")
    seen = set()
    for row in rows:
        if (
            not isinstance(row, dict)
            or row.get("source") != SOURCE
            or row.get("actor_id") != actor.id
            or type(row.get("uid")) is not int
            or row["uid"] in seen
            or any(
                type(row.get(key)) is not int or not -(1 << 31) <= row[key] < (1 << 31)
                for key in ("rBe", "rBf", "rBg")
            )
        ):
            raise ValueError("Missing actual native eWr listener authority")
        seen.add(row["uid"])
    return rows


def has_ap_listener(fight, actor):
    return bool(_listeners(fight, actor))


def notify_resource_pa(fight, actor, stat, *, before_current=None, maximum=False):
    """fff.on notifies only a changed current; fff.or always notifies."""
    from .combat_characteristic_transfer import notify_characteristic_transfers

    notify_characteristic_transfers(
        fight, actor, stat, before_current=before_current, maximum=maximum
    )
    if stat != 2:
        return
    rows = _listeners(fight, actor)
    if not rows:
        return
    from .combat_maximum_resource import _snapshot, _write, effective_maximum

    ap, _, ap_maximum, *_ = _snapshot(actor, 2)
    if not maximum:
        if type(before_current) is not int:
            raise ValueError("Missing actual PA current setter preimage")
        if ap == before_current:
            return
    for row in tuple(rows):
        current_delta = int32(ap - row["rBf"])
        maximum_delta = int32(ap_maximum - row["rBe"])
        row["rBg"] = int32(row["rBg"] + maximum_delta)
        row["rBe"], row["rBf"] = ap_maximum, ap
        # eWr.a: MP.on(current + delta), then MP.or(raw maximum + delta).
        current, raw, *_ = _snapshot(actor, 3)
        set_resource_current(fight, actor, 3, int32(current + current_delta))
        set_resource_maximum(fight, actor, 3, int32(raw + maximum_delta))


def attach_ap_listener(fight, actor, uid):
    from .combat_maximum_resource import _snapshot

    current, _, maximum, *_ = _snapshot(actor, 2)
    _snapshot(actor, 3)
    resource_raw_current(actor, 2)
    resource_raw_current(actor, 3)
    rows = _listeners(fight, actor)
    if any(row["uid"] == uid for row in rows):
        raise ValueError("Duplicate actual eWr listener UID")
    population = getattr(fight, "native_resource_pa_listeners", None)
    if population is None:
        population = {}
        fight.native_resource_pa_listeners = population
    population.setdefault(actor.id, []).append(
        dict(source=SOURCE, actor_id=actor.id, uid=uid, rBe=maximum, rBf=current, rBg=0)
    )


def detach_ap_listener(fight, actor, uid):
    rows = _listeners(fight, actor)
    matched = [row for row in rows if row["uid"] == uid]
    if len(matched) != 1:
        raise ValueError("Missing actual eWr listener for removal")
    rows.remove(matched[0])
    return matched[0]["rBg"]
