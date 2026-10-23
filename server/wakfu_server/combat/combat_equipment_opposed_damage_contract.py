"""Permanent SELF damage subscription followed by one-turn SELF scalar state.

Only definitions are inspected. Existing damage channels, live triggering
identity/predicates, start events, retention and inverse runners own execution.
"""
import ast
from collections.abc import Mapping
import math
from functools import lru_cache
from types import SimpleNamespace

from .combat_definitions import effect_profile, state_profile
from .combat_local_criteria import parse_local_criterion
from .combat_operation_registry import assess_operation


def _criterion(actual, expected):
    return ast.dump(
        parse_local_criterion(actual), include_attributes=False
    ) == ast.dump(parse_local_criterion(expected), include_attributes=False)


def _metadata(
    effect,
    registry,
    family,
    count,
    *,
    duration=0,
    root=False,
    carrier=False,
    channel=None
):
    masks = [None] * 7
    if channel is not None:
        index, event = channel
        masks[index] = [event]
    timing = dict(clock_on_caster=False, clock_on_target=True)
    if not root:
        timing.update(ryE=duration, ryF=0.0, ryG=False, ryH=0, ryI=0.0, esr=False)
    params = effect.get("parameters")
    return (
        all(
            type(effect.get(key)) is int
            for key in (
                "effect_class",
                "parameter_count",
                "variant",
                "minimum_level",
                "maximum_level",
                "native_execution_mode",
            )
        )
        and effect.get("effect_class") == family
        and effect.get("parameter_count") == count
        and effect.get("variant") == 0
        and (effect.get("minimum_level"), effect.get("maximum_level")) == (0, 32767)
        and effect.get("native_execution_mode") == (0 if root else 2)
        and effect.get("native_definition_class") == ("eVE" if root else "eVy")
        and (not root or effect.get("native_active_effect") is False)
        and effect.get("native_target_selector")
        == {"class": "fcE", "mask": 0 if root else 1}
        and (effect.get("area_native"), effect.get("area_class")) == ("point", "anD")
        and tuple(
            tuple(v) if v is not None else None for v in effect.get("target_masks", ())
        )
        == tuple(tuple(v) if v is not None else None for v in masks)
        and effect.get("native_timing_definition") == timing
        and effect.get("application_flag") == ("EFFECT_CARRIER" if carrier else "NONE")
        and effect.get("removal_flag") == ("EFFECT_CARRIER" if carrier else "NONE")
        and tuple(effect.get("native_effect_flags", ())) == ()
        and effect.get("native_localization_enabled") is False
        and effect.get("probability_base") == 100
        and effect.get("probability_per_level") == 0
        and isinstance(effect.get("native_hmi_actions"), Mapping)
        and set(effect["native_hmi_actions"])
        == {"rzc", "rzd", "rze", "rzf", "rzg", "rzh"}
        and not any(effect["native_hmi_actions"].values())
        and isinstance(params, (list, tuple))
        and len(params) == 2 * count
        and all(type(v) in (int, float) and math.isfinite(v) for v in params)
        and assess_operation(effect, characteristic_registry=registry).status
        == "conditional"
    )


def opposed_damage_state_contract(source, compiled, registry):
    """Return None only for the complete reviewed topology, without ID allowlists."""
    if (
        source.get("attachment_field") is not None
        or source.get("unplanned_passive_effect_ids") != ()
    ):
        return "opposed_damage_complete_ordinary_source_required"
    effects, states = compiled.effects, compiled.source_states["states"]
    try:
        if len(source["roots"]) != 1:
            return "opposed_damage_single_carrier_root_required"
        root = effects[str(source["roots"][0])]
        if (
            not _metadata(root, registry, 304, 3, root=True)
            or root.get("criteria", "").strip()
            or root.get("children")
        ):
            return "opposed_damage_root_unqualified"
        permanent, level, chance = effect_profile(
            root, source["native_retained_container"]["level"]
        )["parameters"]
        if tuple(root["parameters"]) != (permanent, 0, 1, 0, -1, 0) or (
            level,
            chance,
        ) != (1, -1):
            return "opposed_damage_root_parameters_unqualified"
        permanent_children = states[str(permanent)]["effect_ids"]
        if len(permanent_children) != 1:
            return "opposed_damage_carrier_children_unqualified"
        damage = effects[str(permanent_children[0])]
        if len(damage["children"]) != 1:
            return "opposed_damage_subscription_children_unqualified"
        waiting_id = damage["children"][0]
        waiting = effects[str(waiting_id)]
        if len(waiting["children"]) != 1:
            return "opposed_damage_wait_children_unqualified"
        apply = effects[str(waiting["children"][0])]
        temporary, level, chance = effect_profile(apply, 1)["parameters"]
        if (
            temporary == permanent
            or tuple(apply["parameters"]) != (temporary, 0, 1, 0, -1, 0)
            or (level, chance) != (1, -1)
            or apply.get("children")
        ):
            return "opposed_damage_temporary_parameters_unqualified"
        scalar_ids = states[str(temporary)]["effect_ids"]
        if len(scalar_ids) != 1:
            return "opposed_damage_temporary_children_unqualified"
        scalar = effects[str(scalar_ids[0])]
        role = registry["effects"].get(str(scalar["effect_class"]), {})
        if (
            role.get("runner") != "eWQ"
            or role.get("dynamic_stat") is not False
            or type(role.get("fixed_stat_id")) is not int
            or role["fixed_stat_id"] in (1, 2, 3, 4)
            or role["fixed_stat_id"] < 0
            or role.get("limit_policy") != "NORMAL"
            or role.get("limit_policy_requires_owned_stack") is not False
            or scalar.get("children")
            or scalar.get("criteria", "").strip()
            or len(scalar["parameters"]) != 2
            or scalar["parameters"][0] <= 0
            or scalar["parameters"][1] != 0
        ):
            return "opposed_damage_scalar_unqualified"
        for effect, family, count, duration, carrier, channel in (
            (damage, 330, 0, -1, True, (3, 2)),
            (waiting, 330, 0, 1, True, (5, 1001)),
            (apply, 304, 3, 0, False, None),
            (scalar, scalar["effect_class"], 1, -1, False, None),
        ):
            if not _metadata(
                effect,
                registry,
                family,
                count,
                duration=duration,
                carrier=carrier,
                channel=channel,
            ):
                return "opposed_damage_effect_metadata_unqualified"
        expected = (
            'not IsTriggeredByIndirectEffect() and GetTeamId("triggeringCaster") '
            '<> GetTeamId("target") and not HasEffectWithSpecificId("target", '
            + str(waiting_id)
            + ")"
        )
        if (
            not _criterion(damage["criteria"], expected)
            or waiting.get("criteria", "").strip()
            or apply.get("criteria", "").strip()
        ):
            return "opposed_damage_live_predicate_unqualified"
        for identity, duration in ((permanent, -1), (temporary, 1)):
            definition = states[str(identity)]
            if (
                type(definition["maximum_level"]) is not int
                or definition["maximum_level"] != 1
            ):
                return "opposed_damage_state_levels_unqualified"
            for state_level in (0, 1):
                profile = state_profile(compiled.source_states, identity, state_level)
                if (
                    type(profile["duration"]) is not int
                    or type(profile["realtime_duration"]) is not int
                    or profile["duration"] != duration
                    or profile["realtime_duration"] != 0
                    or profile["clock_actor"] != "target"
                    or any(
                        profile[k] is not False
                        for k in (
                            "tick_at_turn_end",
                            "additive",
                            "replace",
                            "refresh",
                            "protected",
                            "skip_turn_timer",
                        )
                    )
                ):
                    return "opposed_damage_state_clock_unqualified"
        return None
    except (KeyError, TypeError, ValueError, IndexError):
        return "opposed_damage_missing_or_invalid_native_authority"


@lru_cache(maxsize=None)
def native_opposed_damage_root(reference, root_id):
    """Qualify a copied root with current original state closure, without actors."""
    from .combat_character_copy_equipment import native_copied_equipment_catalog
    from .combat_copied_equipment_plan import copied_equipment_plan
    from .combat_copied_equipment_execution import equipment_effect_definitions
    from .combat_server_spell import compiled_runtime_catalog
    from .combat_static_catalogs import characteristic_registry

    plan = copied_equipment_plan(reference, native_copied_equipment_catalog())
    roots = [root for root in plan["roots"] if root["reference"] == root_id]
    if len(roots) != 1 or roots[0]["effect_class"] != 304:
        return False
    return copied_opposed_damage_root(roots[0], plan["native_retained_container"])


def copied_opposed_damage_root(root, container):
    from .combat_copied_equipment_execution import equipment_effect_definitions
    from .combat_server_spell import compiled_runtime_catalog
    from .combat_static_catalogs import characteristic_registry

    compiled = compiled_runtime_catalog()
    definitions = dict(
        compiled.effects, **equipment_effect_definitions({"roots": [root]})
    )
    source = dict(
        attachment_field=None,
        roots=(root["reference"],),
        unplanned_passive_effect_ids=(),
        native_retained_container=container,
    )
    return (
        opposed_damage_state_contract(
            source,
            SimpleNamespace(effects=definitions, source_states=compiled.source_states),
            characteristic_registry(),
        )
        is None
    )
