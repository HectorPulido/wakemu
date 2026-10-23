"""Common native fau/fat arithmetic and eXt/eXs resource consumption.

Effect selection, parameter evaluation, flags and event reactions belong to
caller. Inputs are authoritative current characteristics and explicit native
contexts. No spell/breed identity whitelist and no identity mitigation.
"""
import math
from wakfu_server.equipment_damage import (
    damage as native_damage,
    ELEMENT_STATS,
    _float,
    _stats,
)

from .combat_damage_contracts import DAMAGE_FAMILIES, HEAL_ELEMENTS


def light_damage_element(source_stats):
    """eYE.a: highest present mastery, ties FIRE/WATER/EARTH/AIR."""
    source = _stats(source_stats)
    candidates = [
        (family, stat)
        for family, stat in ((2, 21), (4, 22), (3, 23), (5, 24))
        if stat in source
    ]
    if not candidates:
        raise ValueError("Missing native LIGHT elemental characteristics")
    return max(candidates, key=lambda item: source[item[1]])[0]


def stasis_resistance_element(target_stats):
    """Original eYE.b: lowest present resistance, native enum tie order."""
    target = _stats(target_stats)
    candidates = [
        (family, stat)
        for family, stat in ((2, 28), (4, 29), (3, 30), (5, 31))
        if stat in target
    ]
    if not candidates:
        raise ValueError("Missing native STASIS resistance characteristics")
    return min(candidates, key=lambda item: target[item[1]])[0]


def _amount(value):
    if type(value) is not int or not 0 <= value < (1 << 31):
        raise ValueError("Invalid native characteristic amount")
    return value


def _flags(*flags):
    if any(type(flag) is not bool for flag in flags):
        raise ValueError("Unknown native arithmetic context")


def _round_native(value, rng):
    floor = math.floor(value)
    fraction = value - floor
    if fraction:
        sample = rng()
        if type(sample) not in (int, float) or not 0 <= sample < 1:
            raise ValueError("Invalid authoritative rounding sample")
        floor += sample < fraction
    return max(1, floor)


def consume_damage(
    value,
    *,
    source_barrier,
    target_armor,
    target_virtual_hp,
    target_hp,
    blocked,
    bypass_armor_and_barrier,
    frozen_stats
):
    """eXt.c/a: block, SOURCE barrier100, target armor97, virtual92, HP1.

    frozen_stats is a complete set of ("source"|"target", stat_id) pairs
    matching fff.sfT. Armor/barrier bypass leaves virtual HP consumption active.
    """
    value, source_barrier, target_armor, target_virtual_hp, target_hp = map(
        _amount, (value, source_barrier, target_armor, target_virtual_hp, target_hp)
    )
    _flags(blocked, bypass_armor_and_barrier)
    if frozen_stats is None:
        raise ValueError("Unknown native characteristic mutability")
    frozen_stats = frozenset(frozen_stats)
    value = math.ceil(_float(_float(value) * _float(0.8))) if blocked else value
    remaining = value
    barrier = armor = 0
    if not bypass_armor_and_barrier:
        if ("source", 100) not in frozen_stats:
            barrier = min(source_barrier, remaining // 2)
            remaining -= barrier
        if ("target", 97) not in frozen_stats:
            armor = min(target_armor, remaining)
            remaining -= armor
    virtual = 0 if ("target", 92) in frozen_stats else min(target_virtual_hp, remaining)
    remaining -= virtual
    hp_loss = 0 if ("target", 1) in frozen_stats else min(target_hp, remaining)
    return dict(
        value=value,
        hp_loss=hp_loss,
        hp_requested=0 if ("target", 1) in frozen_stats else remaining,
        barrier_absorbed=barrier,
        armor_absorbed=armor,
        virtual_hp_absorbed=virtual,
        source_barrier=source_barrier - barrier,
        target_armor=target_armor - armor,
        target_virtual_hp=target_virtual_hp - virtual,
        target_hp=target_hp - hp_loss,
    )


def damage_amount(
    base,
    element,
    source_stats,
    target_stats,
    *,
    arithmetic_context,
    coefficient_mask,
    rng
):
    """Reusable handler: native mastery/resistance followed by consumption.

    arithmetic_context is equipment_damage.damage's explicit audited context.
    Unsupported facing/geometry/modes are rejected by that native formula.
    """
    if type(coefficient_mask) is not int or coefficient_mask not in range(4):
        raise ValueError("Unsupported native damage coefficient mask")
    # fau selects LIGHT's source element before checking coefficient bits.
    if element == 917:
        # fau keeps separate offense/defense elements for STASIS. Project
        # only the selected resistance into the ordinary arithmetic input;
        # retain 917 on the running effect, events and wire.
        defense = stasis_resistance_element(target_stats)
        element = light_damage_element(source_stats)
        target_stats = dict(_stats(target_stats))
        target_stats[ELEMENT_STATS[element][1]] = target_stats[
            ELEMENT_STATS[defense][1]
        ]
    elif element == 1083:
        element = light_damage_element(source_stats)
    # fau.fSy guards mastery/final/indirect by bit1 and both resistance
    # characteristics (elemental and final) by bit2. Front location adds0.
    source_stats = source_stats if coefficient_mask & 1 else {}
    target_stats = target_stats if coefficient_mask & 2 else {}
    arithmetic_context = dict(arithmetic_context)
    if not coefficient_mask & 1:
        arithmetic_context["additional_final"] = 0
        arithmetic_context["additional_mastery"] = 0
        arithmetic_context["encounter_multiplier_bp"] = 10000
    if not coefficient_mask & 2:
        arithmetic_context["additional_resistance"] = 0
    # Native forced MELEE and RANGED may both apply (or neither). The older
    # front formula accepts a single boolean, so project the selected sum.
    if "ranged" in arithmetic_context:
        ranged = arithmetic_context.pop("ranged")
        melee = arithmetic_context["melee"]
        _flags(melee, ranged)
        source_stats = dict(source_stats)
        selected = (source_stats.get(103, 0) if melee else 0) + (
            source_stats.get(104, 0) if ranged else 0
        )
        source_stats[103] = selected
        source_stats[104] = 0
        arithmetic_context["melee"] = True
    value = native_damage(
        base, element, source_stats, target_stats, rng=rng, **arithmetic_context
    )
    return value


def resolve_damage(
    base,
    element,
    source_stats,
    target_stats,
    *,
    arithmetic_context,
    absorption_context,
    coefficient_mask,
    rng
):
    value = damage_amount(
        base,
        element,
        source_stats,
        target_stats,
        arithmetic_context=arithmetic_context,
        coefficient_mask=coefficient_mask,
        rng=rng,
    )
    return consume_damage(value, **absorption_context)


def healing_amount(
    base,
    element,
    source_stats,
    target_stats,
    *,
    critical,
    single_target,
    area,
    melee,
    berserk,
    coefficient_mask,
    additional_mastery,
    additional_final,
    rng,
    ranged=None
):
    """Native fat, elemental mapping matching damage classes1..5.

    Mode bit1 enables source mastery/final bonuses; bit2 heal resistance32
    (stored per thousand, converted with float32 and truncation /10).
    Critical base must already be the selected native critical effect.
    """
    if type(base) is not int or not -(1 << 31) <= base < (1 << 31):
        raise ValueError("Invalid signed native healing base")
    ranged = not melee if ranged is None else ranged
    _flags(critical, single_target, area, melee, ranged, berserk)
    source, target = _stats(source_stats), _stats(target_stats)
    if (
        element not in ELEMENT_STATS
        and element != 6
        or type(coefficient_mask) is not int
        or coefficient_mask not in range(4)
    ):
        raise ValueError("Unsupported native healing element/coefficient mask")
    if (
        type(additional_mastery) is not int
        or type(additional_final) is not int
        or not callable(rng)
    ):
        raise ValueError("Missing native healing bonuses/rounding source")
    mastery = final = 0
    if coefficient_mask & 1:
        mastery = additional_mastery + source.get(20, 0) + source.get(18, 0)
        mastery += source.get(52 if critical else 102, 0)
        mastery += source.get(105, 0) if single_target else 0
        mastery += source.get(106, 0) if area else 0
        mastery += source.get(103, 0) if melee else 0
        mastery += source.get(104, 0) if ranged else 0
        mastery += source.get(107, 0) if berserk else 0
        if element == 6:
            from .combat_element_selection import highest_mastery_element

            selected = highest_mastery_element(source)
            elemental = {1: 21, 2: 22, 3: 23, 4: 24}.get(selected)
        else:
            elemental, _ = ELEMENT_STATS[element]
        if elemental is not None:
            mastery += min(50000, source.get(elemental, 0))
        final = source.get(114, 0) + additional_final
    value = _float(
        _float(base) * _float(_float(1) + _float(_float(mastery) / _float(100)))
    )
    value = _float(float(_float(value * _float(100 + final))) / 100.0)
    resistance = (
        math.trunc(_float(_float(target.get(32, 0)) / _float(10)))
        if coefficient_mask & 2
        else 0
    )
    resisted = _float(_float(value * _float(resistance)) / _float(100))
    value = _float(value - resisted)
    return _round_native(value, rng)


def consume_healing(
    value,
    *,
    target_hp,
    target_max_hp,
    target_virtual_hp,
    target_max_virtual_hp,
    undead,
    bypass_undead,
    frozen_stats
):
    """eXs.fOz: heal HP first, overflow to virtual HP92, discard remainder."""
    value, hp, maximum, virtual, max_virtual = map(
        _amount,
        (value, target_hp, target_max_hp, target_virtual_hp, target_max_virtual_hp),
    )
    _flags(undead, bypass_undead)
    if hp > maximum or virtual > max_virtual or frozen_stats is None:
        raise ValueError("Invalid/unknown native healing target characteristics")
    if undead and not bypass_undead:
        raise ValueError("Native undead conversion requires an eXt damage branch")
    frozen_stats = frozenset(frozen_stats)
    hp_gain = 0 if ("target", 1) in frozen_stats else min(value, maximum - hp)
    virtual_gain = (
        0
        if ("target", 92) in frozen_stats
        else min(value - hp_gain, max_virtual - virtual)
    )
    return dict(
        value=hp_gain + virtual_gain,
        hp_gain=hp_gain,
        virtual_hp_gain=virtual_gain,
        target_hp=hp + hp_gain,
        target_virtual_hp=virtual + virtual_gain,
    )


def healing_resistance_after(
    actual_heal, *, target_max_hp, current, enabled, frozen, minimum, maximum
):
    """eGj.PO: update characteristic32 after actual eXs healing.

    Caller resolves actor/fight guards (type0/5 or eHQ.pUr, dnz, fcb mode)
    into enabled. Characteristic existence, mutability and native bounds must
    be supplied explicitly. Uses Java float32 operations and f2i truncation.
    """
    # eXs.fOz uses PA.nG's raw delta, which may be negative when HP.on
    # collapses a copied over-maximum raw current. eGj.PO accepts signed int.
    if type(actual_heal) is not int or not -(1 << 31) <= actual_heal < (1 << 31):
        raise ValueError("Invalid native signed actual healing amount")
    _amount(target_max_hp)
    _flags(enabled, frozen)
    if (
        any(type(v) is not int for v in (current, minimum, maximum))
        or not minimum <= current <= maximum
    ):
        raise ValueError("Invalid native heal resistance characteristic bounds")
    if not enabled or frozen:
        return current
    if target_max_hp == 0:
        raise ValueError("Unknown/zero native healing maximum HP")
    increment = _float(
        _float(_float(_float(actual_heal) / _float(target_max_hp)) / _float(5))
        * _float(1000)
    )
    return min(maximum, max(minimum, math.trunc(_float(_float(current) + increment))))


def resolve_healing(
    base,
    element,
    source_stats,
    target_stats,
    *,
    arithmetic_context,
    consumption_context,
    resistance_context
):
    """Native fat -> eXs consumption -> eGj.PO with explicit contexts."""
    value = healing_amount(
        base, element, source_stats, target_stats, **arithmetic_context
    )
    result = consume_healing(value, **consumption_context)
    result["target_heal_resistance"] = healing_resistance_after(
        result["value"], **resistance_context
    )
    return result
