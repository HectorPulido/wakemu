"""Native eXt.fOA parameter contract and fOG/fOI flags, without spell IDs."""
import math
from .combat_parameters import parameter_value
from wakfu_server.equipment_damage import _float


def damage_effect_level(*, context_override, container_level):
    """eZR.fRR: context Oh!=-1 wins; otherwise container cmZ, else0."""
    if context_override is not None and type(context_override) is not int:
        raise ValueError("Unknown native effect level override")
    if container_level is not None and (
        type(container_level) is not int or not -32768 <= container_level <= 32767
    ):
        raise ValueError("Invalid native container short level")
    level = (
        context_override if context_override not in (None, -1) else container_level or 0
    )
    return ((level + 32768) % 65536) - 32768


def damage_parameter_specification(parameters, level):
    """Decode native shape and modes without actor HP or rounding draws."""
    if len(parameters) not in (2, 4, 6):
        raise ValueError("Unsupported eXt parameter count (native expects1..3)")
    values = [
        parameter_value(parameters, i, level) for i in range(len(parameters) // 2)
    ]
    mask = values[1] if len(values) > 1 else 3
    if mask not in range(4):
        raise ValueError("Unknown coefficient bits")
    kind = ((values[2] + 128) % 256) - 128 if len(values) > 2 else 0
    if kind not in range(7):
        kind = 0
    base = values[0]
    return dict(base=base, coefficient_mask=mask, base_kind=kind, level=level)


def interpret_damage_parameters(
    parameters, level, *, hp_context, rng, allow_signed_base=False
):
    """Evaluate eVE parameter pairs at eXt.fRR's authoritative level.

    far1..6 use HP1 only (exclude virtual HP92). hp_context supplies
    source/target current/max values explicitly when percentages require them.
    Unknown far byte values map to CLASSIC natively; signed-byte conversion is
    preserved. Integer multiplication precedes float32 percentage conversion.
    """
    specification = damage_parameter_specification(parameters, level)
    base = specification["base"]
    mask = specification["coefficient_mask"]
    kind = specification["base_kind"]
    if kind:
        side = "source" if kind in (1, 2, 3) else "target"
        mode = ((kind - 1) % 3) + 1
        keys = (
            [side + "_max_hp"]
            if mode == 1
            else [side + "_hp"]
            if mode == 2
            else [side + "_max_hp", side + "_hp"]
        )
        if not isinstance(hp_context, dict) or any(
            type(hp_context.get(k)) is not int or hp_context[k] < 0 for k in keys
        ):
            raise ValueError("Missing native percent-HP context")
        hp = hp_context[keys[0]] - (hp_context[keys[1]] if mode == 3 else 0)
        product = ((hp * base + (1 << 31)) % (1 << 32)) - (1 << 31)
        amount = _float(_float(product) / _float(100))
        floor = math.floor(amount)
        if amount != floor:
            sample = rng()
            if type(sample) not in (float, int) or not 0 <= sample < 1:
                raise ValueError("Missing authoritative percent rounding sample")
            floor += sample < amount - floor
        base = floor
    if type(allow_signed_base) is not bool:
        raise ValueError("Explicit signed parameter policy required")
    minimum = -(1 << 31) if allow_signed_base else 0
    if not minimum <= base < (1 << 31):
        raise ValueError("Unsupported negative damage parameter result")
    return dict(base=base, coefficient_mask=mask, base_kind=kind, level=level)


def interpret_damage_flags(flags, *, container_type, executable, actors_present):
    """eVl native flag IDs; return unhandled flags for caller's policy.

    Critical comes from dd(1) variant, NOT eVl. executable is eXt.bbs's
    authoritative result. container_type None means no container, not unknown.
    """
    if (
        type(executable) is not bool
        or type(actors_present) is not bool
        or (container_type is not None and type(container_type) is not int)
    ):
        raise ValueError("Unknown native damage execution context")
    flags = frozenset(flags)
    if any(type(flag) is not int for flag in flags):
        raise ValueError("Invalid native effect flags")
    return dict(
        indirect=34 not in flags and container_type not in (11, 12),
        block_enabled=executable and actors_present and 2 not in flags,
        bypass_armor_and_barrier=28 in flags,
        unhandled_flags=tuple(sorted(flags - {2, 28, 34})),
    )


def damage_mastery_context(
    flags,
    *,
    source_xy,
    target_xy,
    source_radius,
    target_radius,
    source_total_hp,
    source_total_max_hp,
    source_has_berserk=True,
):
    """fau.fSD/eYE: area4, single22, forced melee23/ranged24.

    ala.c subtracts BOTH actor bcL radii from each XY delta before summing.
    Berserk uses HP1 PLUS virtualHP92, unlike far percentage base modes.
    Both forced range flags can be true natively; neither is the complement
    of the other when flags are present.
    """
    flags = frozenset(flags)
    inputs = (
        *source_xy,
        *target_xy,
        source_radius,
        target_radius,
    ) + ((source_total_hp, source_total_max_hp) if source_has_berserk else ())
    if (
        type(source_has_berserk) is not bool
        or (
            not source_has_berserk
            and (source_total_hp is not None or source_total_max_hp is not None)
        )
        or len(source_xy) != 2
        or len(target_xy) != 2
        or any(type(v) is not int for v in inputs)
        or min(inputs[4:]) < 0
    ):
        raise ValueError("Unknown native mastery geometry/HP context")
    radius = source_radius + target_radius
    distance = sum(max(0, abs(a - b) - radius) for a, b in zip(source_xy, target_xy))
    forced = bool(flags & {23, 24})
    berserk = (
        source_has_berserk
        and source_total_max_hp > 0
        and _float(
            _float(_float(source_total_hp) / _float(source_total_max_hp)) * _float(100)
        )
        < 50
    )
    return dict(
        single_target=22 in flags,
        area=4 in flags,
        melee=23 in flags or (not forced and distance <= 2),
        ranged=24 in flags or (not forced and distance > 2),
        berserk=berserk,
    )
