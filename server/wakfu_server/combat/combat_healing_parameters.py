"""eXs.fOA/fOC contracts, proven from the bundled native client.

Parameter pairs, far value modes and pre-formula percent rounding are shared
with eXt. Actor presence and critical variant must come from authoritative
execution context. Geometry uses the same independent eYE range predicates.
"""
from .combat_damage_parameters import (
    interpret_damage_parameters,
    damage_mastery_context,
)


def interpret_healing_parameters(parameters, level, *, hp_context, rng):
    """Native eXs expects 1..3 evaluated parameters (2..6 base/growth items).

    p0 base, p1 coefficient mask(default3), p2 signed-byte far(default0).
    Signed p0 is preserved: native fat.fSy clamps the computed result to1
    before eZR applies a later context override. Unknown mask bits reject.
    """
    return interpret_damage_parameters(
        parameters, level, hp_context=hp_context, rng=rng, allow_signed_base=True
    )


healing_mastery_context = damage_mastery_context


def interpret_healing_flags(
    flags,
    *,
    critical_variant,
    source_present,
    target_present,
    target_has_hp,
    undead,
    native_fKK,
    native_aZB
):
    """eXs critical=dd(1), bypass-undead=eVl.rxd native ID33.

    The native undead branch delegates to eXt using a synthetic effect ID;
    this helper identifies that branch but never executes it. Flags beyond
    mastery/bypass remain explicit for the caller's policy.
    """
    flags = frozenset(flags)
    if any(type(v) is not int for v in flags) or any(
        type(v) is not bool
        for v in (
            critical_variant,
            source_present,
            target_present,
            target_has_hp,
            undead,
            native_fKK,
            native_aZB,
        )
    ):
        raise ValueError("Unknown native healing execution context")
    execute = source_present and target_present and target_has_hp
    convert = execute and undead and 33 not in flags
    synthetic = {
        (True, True): -11,
        (True, False): -3,
        (False, True): -8,
        (False, False): -12,
    }
    return dict(
        executable=execute,
        critical=critical_variant,
        bypass_undead=33 in flags,
        converts_to_damage=convert,
        undead_damage_effect_id=synthetic[native_fKK, native_aZB] if convert else None,
        unhandled_flags=tuple(sorted(flags - {4, 22, 23, 24, 33})),
    )
