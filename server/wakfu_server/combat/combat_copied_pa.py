"""Actual eHI copied ffh raw current authority and original fff setters."""
from copy import deepcopy
import math
from .combat_casting_range import int32
from .combat_character_copy_metadata import native_copy_characteristics

SOURCE = "eHI.pRU.ffh.a"


def copied_pa_present(actor):
    return getattr(actor, "native_copy_pa_source", None) is not None


def copied_raw_current(actor, stat):
    source = getattr(actor, "native_copy_pa_source", None)
    raw = getattr(actor, "effect_characteristic_raw_currents", None)
    if (
        not isinstance(source, dict)
        or source.get("producer") != SOURCE
        or source.get("actor_id") != actor.id
        or source.get("profile") != 2382
        or type(source.get("effect_reference")) is not int
        or type(source.get("source_actor_id")) is not int
        or not isinstance(raw, dict)
        or type(raw.get(stat)) is not int
        or not -(1 << 31) <= raw[stat] < (1 << 31)
    ):
        raise ValueError("Missing actual copied PA raw-current authority")
    minimum, maximum = actor.effect_minima[stat], actor.effect_maxima[stat]
    if actor.effect_stats[stat] != max(minimum, min(maximum, raw[stat])):
        raise ValueError(
            "Copied PA raw/effective current mismatch: "
            f"actor={actor.id} PC={stat} raw={raw[stat]} "
            f"effective={actor.effect_stats[stat]} minimum={minimum} maximum={maximum}"
        )
    return raw[stat]


def copied_shift_result(actor, stat, amount, *, subtract=False):
    raw = copied_raw_current(actor, stat)
    current = actor.effect_stats[stat]
    minimum, maximum = actor.effect_minima[stat], actor.effect_maxima[stat]
    if stat in actor.effect_frozen:
        return raw, current, 0
    requested = (
        (minimum if amount > current - minimum else int32(raw - amount))
        if subtract
        else (maximum if amount > maximum - current else int32(raw + amount))
    )
    definition = native_copy_characteristics()["fresh_characteristics"][str(stat)]
    upper = definition["hard_maximum"] if definition["over_max_current"] else maximum
    after = max(minimum, min(upper, requested))
    effective = max(minimum, min(maximum, after))
    return after, effective, int32(raw - after if subtract else after - raw)


def set_copied_current(fight, actor, stat, requested):
    copied_raw_current(actor, stat)
    if stat in actor.effect_frozen:
        return
    definition = native_copy_characteristics()["fresh_characteristics"][str(stat)]
    minimum, maximum = actor.effect_minima[stat], actor.effect_maxima[stat]
    upper = definition["hard_maximum"] if definition["over_max_current"] else maximum
    raw = max(minimum, min(upper, int32(requested)))
    before = actor.effect_stats[stat]
    actor.effect_characteristic_raw_currents[stat] = raw
    effective = max(minimum, min(maximum, raw))
    actor.effect_stats[stat] = effective
    if stat in (1, 2, 3):
        setattr(actor, {1: "hp", 2: "ap", 3: "mp"}[stat], effective)
    if stat in (2, 3):
        actor.effect_resource_raw_currents[stat] = raw
    from .combat_resource_pa_notifications import notify_resource_pa

    notify_resource_pa(fight, actor, stat, before_current=before)


def shift_copied_current(fight, actor, stat, amount, *, subtract=False):
    raw, effective, actual = copied_shift_result(actor, stat, amount, subtract=subtract)
    set_copied_current(fight, actor, stat, raw)
    return actual


def set_copied_maximum(fight, actor, stat, requested):
    """Actual fff.or for every copied PA, including WP and fixed stats."""
    raw = copied_raw_current(actor, stat)
    definition = native_copy_characteristics()["fresh_characteristics"][str(stat)]
    raw_maximum = max(actor.effect_base_minima[stat], int32(requested))
    product = int32(raw_maximum * actor.effect_percentages[stat])
    adjustment = abs(product) // 100 * (1 if product >= 0 else -1)
    maximum = max(
        definition["hard_minimum"],
        min(definition["hard_maximum"], int32(raw_maximum + adjustment)),
    )
    if stat not in actor.effect_frozen and not definition["over_max_current"]:
        raw = min(raw, maximum)
    before = actor.effect_stats[stat]
    actor.effect_characteristic_raw_currents[stat] = raw
    actor.effect_base_maxima[stat] = raw_maximum
    actor.effect_maxima[stat] = maximum
    actor.effect_stats[stat] = max(actor.effect_minima[stat], min(maximum, raw))
    if stat in (1, 2, 3):
        setattr(actor, {1: "hp", 2: "ap", 3: "mp"}[stat], actor.effect_stats[stat])
        setattr(actor, {1: "max_hp", 2: "max_ap", 3: "max_mp"}[stat], maximum)
    if stat in (2, 3):
        actor.effect_resource_raw_currents[stat] = raw
    from .combat_resource_pa_notifications import notify_resource_pa

    notify_resource_pa(fight, actor, stat, before_current=before, maximum=True)


def copied_current_stat_result(actor, stat, requested, *, family, percent):
    from wakfu_server.equipment_damage import _float

    if family not in ("eWQ", "eWR") or type(percent) is not bool:
        raise ValueError("Missing actual copied current-stat operation")
    amount = requested
    if percent:
        amount = math.trunc(
            _float(
                _float(_float(actor.effect_stats[stat]) / _float(100))
                * _float(requested)
            )
        )
    raw, current, actual = copied_shift_result(
        actor, stat, amount, subtract=family == "eWR"
    )
    return dict(
        raw_current=raw,
        current=current,
        actual=actual,
        requested=requested,
        stat_changed=current != actor.effect_stats[stat],
    )


def install_copied_pa_pool(actor, characteristics, *, metadata, source_record):
    """Install actual ffh.a(tB) operands; preserve existing fresh frozen flags."""
    from .combat_character_copy_codec import CopyCharacteristic
    from .combat_resource_pa_notifications import RAW_SOURCE

    canonical = native_copy_characteristics()
    if metadata != canonical:
        raise ValueError("Missing exact original copied PA constructor metadata")
    order = canonical["native_characteristic_order"]
    if (
        not isinstance(characteristics, tuple)
        or [
            row.identifier for row in characteristics if type(row) is CopyCharacteristic
        ]
        != order
        or len(characteristics) != len(order)
        or not isinstance(source_record, dict)
        or source_record.get("producer") != SOURCE
        or source_record.get("actor_id") != actor.id
        or source_record.get("profile") != 2382
        or any(
            type(source_record.get(key)) is not int
            for key in ("effect_reference", "source_actor_id")
        )
        or source_record.get("copied_raw_characteristics")
        != [
            [row.identifier, row.current, row.minimum, row.maximum, row.percentage]
            for row in characteristics
        ]
        or not isinstance(actor.effect_frozen, frozenset)
    ):
        raise ValueError("Missing actual ordered copied PA pool/source")
    mappings = {
        name: {}
        for name in (
            "effect_stats",
            "effect_minima",
            "effect_maxima",
            "effect_base_minima",
            "effect_base_maxima",
            "effect_percentages",
        )
    }
    raw = {}
    for row in characteristics:
        values = (row.current, row.minimum, row.maximum, row.percentage)
        if any(
            type(value) is not int or not -(1 << 31) <= value < (1 << 31)
            for value in values
        ):
            raise ValueError("Invalid copied raw PA operand")
        definition = canonical["fresh_characteristics"][str(row.identifier)]
        low, high = definition["hard_minimum"], definition["hard_maximum"]
        product = int32(row.maximum * row.percentage)
        adjustment = abs(product) // 100 * (1 if product >= 0 else -1)
        maximum = max(low, min(high, int32(row.maximum + adjustment)))
        minimum = max(low, min(high, row.minimum))
        if row.minimum > row.maximum:
            raise ValueError("Invalid copied raw PA bounds")
        raw[row.identifier] = row.current
        for name, value in (
            ("effect_stats", max(minimum, min(maximum, row.current))),
            ("effect_minima", minimum),
            ("effect_maxima", maximum),
            ("effect_base_minima", row.minimum),
            ("effect_base_maxima", row.maximum),
            ("effect_percentages", row.percentage),
        ):
            mappings[name][row.identifier] = value
    for name, mapping in mappings.items():
        setattr(actor, name, mapping)
    actor.effect_characteristic_raw_currents = raw
    actor.native_copy_pa_source = deepcopy(source_record)
    actor.effect_resource_raw_currents = {stat: raw[stat] for stat in (2, 3)}
    actor.native_resource_raw_current_source = RAW_SOURCE
    for stat, current_name, maximum_name in (
        (1, "hp", "max_hp"),
        (2, "ap", "max_ap"),
        (3, "mp", "max_mp"),
    ):
        setattr(actor, current_name, actor.effect_stats[stat])
        setattr(actor, maximum_name, actor.effect_maxima[stat])
    actor.initiative = actor.effect_stats[35]
