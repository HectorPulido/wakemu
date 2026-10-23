"""Pure eYn913 group descriptor; live PA and child-domain proof stay explicit.

A parsed PC selector never grants permission to validate descendants at their
incoming parent level: the group computes its actual child level at execution.
"""
from collections.abc import Mapping
import math

from .combat_effect_groups import decode_group_mode


def parse(effect, profile, *, characteristics=None):
    if effect.get("effect_class") != 913:
        raise ValueError("Wrong native eYn operation family")
    count, raw = effect.get("parameter_count"), effect.get("parameters")
    values = profile.get("parameters") if isinstance(profile, Mapping) else None
    if (
        type(count) is not int
        or count not in (9, 10, 11, 12)
        or not isinstance(raw, (tuple, list))
        or len(raw) != 2 * count
        or not isinstance(values, (tuple, list))
        or len(values) != count
        or any(type(v) not in (int, float) or not math.isfinite(v) for v in raw)
        or any(type(v) is not int or not -(1 << 31) <= v < (1 << 31) for v in values)
    ):
        raise ValueError("Malformed native eYn parameters")
    mode = decode_group_mode(values[:6], raw_target_parameter=raw[4])
    from .combat_native_events import validate_group_registration_flags

    flags = effect.get("native_effect_flags")
    if not isinstance(flags, (tuple, list)):
        raise ValueError("Missing native eYn registration flag authority")
    validate_group_registration_flags(
        flags,
        active=False,
        constructor=True,
        effect=effect,
        reference=effect.get("_capability_reference"),
    )
    # Original eYn.C narrows through signed byte/ffw; unsigned export keys
    # preserve the same enum identity (132 and -124 are one characteristic).
    stat_id = values[6] & 255
    if characteristics is None:
        from .combat_actor_snapshot import native_actor_catalog

        characteristics = native_actor_catalog()["characteristics"]
    if not isinstance(characteristics, Mapping):
        raise ValueError("Missing native PA characteristic enum authority")
    known = str(stat_id) in characteristics
    input_mode = values[10] if count >= 11 else 0
    rounding = values[11] if count >= 12 else 1
    return dict(
        group_mode=mode,
        stat_id=stat_id if known else None,
        raw_stat_id=stat_id,
        select_caster=values[7] == 1,
        parameter_count=count,
        input_mode=input_mode,
        effective_input_mode=input_mode if input_mode in (1, 2, 3, 4) else 0,
        rounding=rounding,
        effective_rounding=rounding if rounding in (2, 3) else 1,
        unknown_stat_preserves_parent_level=not known,
        child_level_domain=(-32768, 32767),
    )


def required_context(parsed):
    requirements = ["native_runner_lifecycle", "native_dynamic_child_level"]
    if parsed["stat_id"] is not None:
        requirements.extend(
            (
                "native_selected_characteristic_pa",
                "native_characteristic_child_level_domain",
            )
        )
    if parsed["group_mode"].actor_rebind:
        requirements.append("native_group_actor_rebinding")
    if not parsed["group_mode"].on_target:
        requirements.append("native_group_cell_targets")
    if parsed["group_mode"].relative_probability:
        requirements.extend(("relative_group_candidates", "native_group_rng"))
    return tuple(requirements)


def child_level_at_snapshot(effect, level, *, current, maximum):
    """Arithmetic witness only; one current PA value is not a future-event domain."""
    from .combat_characteristic_level_group import characteristic_group_override

    return characteristic_group_override(
        effect, level, current=current, maximum=maximum
    )


def child_domain_witnesses(effect, effects, states):
    """Reuse the complete signed-short invariant/clamped-state proof.

    Every returned child witness still needs its actual typed operation and
    provider approval. Native PA values are not guessed or sampled here.
    """
    from .combat_equipment_hp_group_parser import child_domain_witnesses as prove

    return prove(effect, effects, states)
