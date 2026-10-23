"""Native fau damage arithmetic for explicit, already selected effect contexts.

This does not select spell branches, roll a critical cast, simulate armor/block,
resolve rear/side geometry, or turn an unsupported effect into flat damage.
"""
import math
import random
import struct
from decimal import Decimal, ROUND_CEILING
from wakfu_server.equipment_stats import bonuses

# Running-effect class IDs (eVi), distinct from eVg elemental enum identifiers.
ELEMENT_STATS = {1: (None, None), 2: (21, 28), 3: (23, 30), 4: (22, 29), 5: (24, 31)}


def _float(value):
    return struct.unpack(">f", struct.pack(">f", value))[0]


def _stats(values):
    if not isinstance(values, dict) or any(
        type(k) is not int or type(v) is not int for k, v in values.items()
    ):
        raise ValueError("Native damage statistics must be integer mappings")
    return values


def inputs(character, *, build_index=None):
    evaluated = bonuses(character, build_index=build_index)
    stats = evaluated["stats"]
    return dict(
        stats=stats,
        critical_chance=max(0, min(100, stats.get(9, 0))),
        unsupported=evaluated["unsupported"],
    )


def resistance_multiplier(points, *, ignore_cap=False):
    if type(points) is not int or type(ignore_cap) is not bool:
        raise ValueError("Invalid native resistance input")
    exponent = _float(_float(points) / _float(100))
    power = math.pow(_float(0.8), exponent)
    # fau.b constructs BigDecimal(double), then CEILING to two decimal places.
    rounded = float(
        Decimal.from_float(power).quantize(Decimal("0.01"), rounding=ROUND_CEILING)
    )
    return rounded if ignore_cap else max(0.1, rounded)


def damage(
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
    front,
    indirect=False,
    ignore_resistance_cap=False,
    rng=None,
    localization=None,
    additional_final=0,
    additional_mastery=0,
    additional_resistance=0,
    encounter_multiplier_bp=10000,
):
    """Compute the native normal-front result with caller-selected cast variant.

    Every context is explicit: critical base damage must already be the actual
    critical effect branch. `melee` must reflect effect flags, not just a guessed
    distance. Existing bare guards must not be bypassed to call this helper.
    """
    if (
        type(base) is not int
        or not 0 <= base < (1 << 31)
        or element not in ELEMENT_STATS
    ):
        raise ValueError("Invalid native base damage or running-effect element")
    if type(encounter_multiplier_bp) is not int or not 0 < encounter_multiplier_bp < (
        1 << 31
    ):
        raise ValueError("Invalid explicit encounter damage multiplier")
    flags = (
        critical,
        single_target,
        area,
        melee,
        berserk,
        front,
        indirect,
        ignore_resistance_cap,
    )
    if any(type(flag) is not bool for flag in flags):
        raise ValueError("Unknown native damage flags")
    if localization is None:
        if not front:
            raise ValueError("Non-front damage requires explicit native localization")
        localization = "FRONT"
    if localization not in ("FRONT", "SIDE", "BACK") or front != (
        localization == "FRONT"
    ):
        raise ValueError("Native localization conflicts with explicit front flag")
    # fau.fSH disables localization for neutral eVg.rpe.
    location = "FRONT" if element == 1 else localization
    source, target = _stats(source_stats), _stats(target_stats)
    if any(
        type(v) is not int or not -(1 << 31) <= v < (1 << 31)
        for v in (additional_mastery, additional_resistance)
    ):
        raise ValueError("Invalid native damage auxiliary fields")
    mastery = (
        additional_mastery + source.get(20, 0) + source.get(52 if critical else 102, 0)
    )
    if location == "BACK":
        mastery += source.get(16, 0)
    if single_target:
        mastery += source.get(105, 0)
    if area:
        mastery += source.get(106, 0)
    mastery += source.get(103 if melee else 104, 0)
    if berserk:
        mastery += source.get(107, 0)
    elemental_mastery, elemental_resistance = ELEMENT_STATS[element]
    if elemental_mastery is not None:
        mastery += min(50000, source.get(elemental_mastery, 0))
    resistance = (
        additional_resistance
        + target.get(27, 0)
        + (target.get(elemental_resistance, 0) if elemental_resistance else 0)
    )
    if critical:
        resistance += target.get(95, 0)
    if location == "BACK":
        resistance += target.get(17, 0)
    factor = _float(_float(1) + _float(_float(mastery) / _float(100)))
    factor = _float(
        float(factor)
        * resistance_multiplier(resistance, ignore_cap=ignore_resistance_cap)
    )
    value = _float(_float(base) * factor)
    # fau.fSL multiplies before final bonuses, independently of mask bits.
    value = _float(
        value
        * _float(
            _float(100 + ({"FRONT": 0, "SIDE": 10, "BACK": 25}[location])) / _float(100)
        )
    )
    if type(additional_final) is not int or not -(1 << 31) <= additional_final < (
        1 << 31
    ):
        raise ValueError("Invalid native faq final modifier")
    final = (
        source.get(48, 0) + (source.get(101, 0) if indirect else 0) + additional_final
    )
    final_factor = _float(
        _float(100 + max(-50, final) - target.get(49, 0)) / _float(100)
    )
    value = _float(value * final_factor)
    if encounter_multiplier_bp != 10000:
        # Explicit encounter policy is independent of native final percentages.
        # Keep float32 precision until the existing single floor/RNG decision.
        value = _float(value * _float(_float(encounter_multiplier_bp) / _float(10000)))
    floor = math.floor(value)
    probability = value - floor
    # UP.bt/GT.l is stochastic rounding, not Math.round or truncation.
    if probability:
        sample = (random.random if rng is None else rng)()
        if type(sample) not in (int, float) or not 0 <= sample < 1:
            raise ValueError("Invalid authoritative random sample")
        if sample < probability:
            floor += 1
    return max(1, floor)
