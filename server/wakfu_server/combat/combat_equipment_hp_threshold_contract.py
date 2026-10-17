"""Finite native permanent carrier / HP threshold / generic-ID removal topology.

Admission only: native HP views, subscriptions, retained identity, stat mutation
and dispel remain owned by the existing runners. No HP or stat default is added.
"""
import ast
from collections.abc import Mapping

from .combat_definitions import effect_profile, state_profile
from .combat_local_criteria import parse_local_criterion
from .combat_operation_registry import assess_operation


def _criterion(expression, generic_id, threshold, *, high, removal):
    presence = "" if removal else "not "
    comparison = ("<" if removal else ">=") if high else (">" if removal else "<=")
    expected = parse_local_criterion(
        f'{presence}HasEffectWithSpecificId("target", {generic_id}) and '
        f'GetTotalHpInPercent("target") {comparison} {threshold}'
    )
    return ast.dump(parse_local_criterion(expression)) == ast.dump(expected)


def _clock(effect, duration):
    row = effect.get("native_timing_definition", {})
    return (
        isinstance(row, Mapping)
        and set(row)
        == {
            "esr",
            "ryE",
            "ryF",
            "ryG",
            "ryH",
            "ryI",
            "clock_on_caster",
            "clock_on_target",
        }
        and row.get("esr") is False
        and type(row.get("ryE")) is int
        and row["ryE"] == duration
        and all(type(row.get(key)) in (int, float) for key in ("ryF", "ryH", "ryI"))
        and row.get("ryF") == 0
        and row.get("ryG") is False
        and row.get("ryH") == row.get("ryI") == 0
        and row.get("clock_on_caster") is False
        and row.get("clock_on_target") is True
    )


def _shape(effect, registry, maximum, *, family, duration, carrier=False, root=False):
    selector = effect.get("native_target_selector", {})
    masks = effect.get("target_masks")
    expected_masks = (None, None, None, (1, 2), None, (1001, 1002), None)
    normalized_masks = (
        tuple(tuple(row) if row else None for row in masks) if masks is not None else ()
    )
    flags = tuple(effect.get("native_effect_flags", ()))
    return (
        effect["effect_class"] == family
        and all(
            type(effect.get(key)) is int
            for key in (
                "effect_class",
                "variant",
                "parameter_count",
                "minimum_level",
                "maximum_level",
                "native_execution_mode",
            )
        )
        and isinstance(effect.get("parameters"), (tuple, list))
        and all(type(value) in (int, float) for value in effect["parameters"])
        and effect.get("parameter_count")
        == ({304: 3, 330: 1, 400: 1, 421: 1, 80: 1, 120: 1}[family])
        and type(effect.get("variant")) is int
        and effect["variant"] == 0
        and isinstance(selector, Mapping)
        and type(selector.get("mask")) is int
        and selector == {"mask": 0 if root else 1, "class": "fcE"}
        and effect.get("native_definition_class") == ("eVE" if root else "eVy")
        and effect.get("native_execution_mode") == (0 if root else 2)
        and effect.get("area_native") == ("empty" if root else "point")
        and effect.get("area_class") == ("anA" if root else "anD")
        and effect.get("native_localization_enabled") is False
        and (not root or effect.get("native_active_effect") is False)
        and isinstance(effect.get("native_hmi_actions"), Mapping)
        and set(effect["native_hmi_actions"])
        == {"rzc", "rzd", "rze", "rzf", "rzg", "rzh"}
        and all(
            isinstance(rows, (tuple, list)) and not rows
            for rows in effect["native_hmi_actions"].values()
        )
        and isinstance(masks, (tuple, list))
        and all(
            row is None
            or (
                isinstance(row, (tuple, list))
                and all(type(value) is int for value in row)
            )
            for row in masks
        )
        and normalized_masks == (expected_masks if carrier else (None,) * 7)
        and all(type(flag) is int for flag in flags)
        and flags in (((1,), (1, 17)) if carrier else (((),) if root else ((17,),)))
        and effect.get("application_flag") == ("EFFECT_CARRIER" if carrier else "NONE")
        and effect.get("removal_flag") == ("EFFECT_CARRIER" if carrier else "NONE")
        and type(effect["minimum_level"]) is int
        and type(effect["maximum_level"]) is int
        and effect["minimum_level"] <= 0 <= maximum <= effect["maximum_level"]
        and type(effect["probability_base"]) in (int, float)
        and type(effect["probability_per_level"]) in (int, float)
        and effect["probability_base"] == 100
        and effect["probability_per_level"] == 0
        and assess_operation(effect, characteristic_registry=registry).status
        == "conditional"
        and (
            dict(effect["native_timing_definition"])
            == {"clock_on_caster": False, "clock_on_target": True}
            if root
            else _clock(effect, duration)
        )
    )


def hp_threshold_state_contract(source, compiled, registry):
    """Return None only for the complete source-derived finite switch topology.

    Whole-passive completeness and inventory ownership are checked by the
    caller before this structural qualification. Thresholds are deliberately
    limited to the observed native high-90 and low-50/75 shapes.
    """
    roots = source.get("roots", ())
    if source.get("attachment_field") is not None or len(roots) not in (1, 2):
        return "hp_threshold_requires_ordinary_state_roots"
    try:
        if registry["effects"].get("400", {}).get("runner") != "eXE":
            return "hp_threshold_native_null_runner_unqualified"
        source_level = source["native_retained_container"]["level"]
        if type(source_level) is not int or not 0 <= source_level <= 32767:
            return "hp_threshold_source_level_unqualified"
        for reference in roots:
            if type(reference) is not int or reference <= 0:
                return "hp_threshold_root_identity_unqualified"
            root = compiled.effects[str(reference)]
            values = effect_profile(root, source_level)
            if (
                root.get("children")
                or root.get("criteria", "").strip()
                or len(root["parameters"]) != 6
                or tuple(root["parameters"])[1::2] != (0, 0, 0)
                or values["probability"] != 100
                or not root["minimum_level"] <= source_level <= root["maximum_level"]
            ):
                return "hp_threshold_initial_state_unqualified"
            state_id, applied_level, chance = values["parameters"]
            if (
                type(state_id) is not int
                or type(applied_level) is not int
                or applied_level <= 0
                or chance != -1
            ):
                return "hp_threshold_initial_parameters_unqualified"
            definition = compiled.source_states["states"][str(state_id)]
            maximum = definition["maximum_level"]
            if type(maximum) is not int or not applied_level <= maximum <= 32767:
                return "hp_threshold_state_level_unqualified"
            if not _shape(root, registry, maximum, family=304, duration=-1, root=True):
                return "hp_threshold_initial_state_shape_unqualified"
            if (
                definition["duration_per_level"] != 0
                or definition["realtime_duration_per_level"] != 0
            ):
                return "hp_threshold_state_clock_growth_unqualified"
            state = state_profile(compiled.source_states, state_id, applied_level)
            if (
                state["duration"] != -1
                or state["realtime_duration"] != 0
                or state["clock_actor"] != "target"
                or state["tick_at_turn_end"] is not False
                or state["additive"] is not True
                or state["replace"] is not False
                or state["refresh"] is not False
                or state["protected"] is not False
                or state["skip_turn_timer"] is not False
                or len(definition["effect_ids"]) != 2
                or tuple(state["effects"]) != tuple(definition["effect_ids"])
            ):
                return "hp_threshold_permanent_carrier_unqualified"
            for requested in (0, maximum):
                branch = state_profile(compiled.source_states, state_id, requested)
                if tuple(branch["effects"]) != tuple(definition["effect_ids"]):
                    return "hp_threshold_state_level_branch_unqualified"
            # Each child covers the entire closed state level interval below;
            # native level eligibility consists only of inclusive min/max.
            carrier, marker = (compiled.effects[str(key)] for key in state["effects"])
            if (
                not _shape(
                    carrier, registry, maximum, family=330, duration=-1, carrier=True
                )
                or carrier.get("criteria", "").strip()
                or tuple(carrier["parameters"]) != (0, 0)
                or len(carrier["children"]) != 2
                or not _shape(marker, registry, maximum, family=400, duration=-1)
                or marker.get("children")
                or marker.get("criteria", "").strip()
                or tuple(marker["parameters"]) != (0, 1)
            ):
                return "hp_threshold_subscription_or_marker_unqualified"
            activation, removal = (
                compiled.effects[str(key)] for key in carrier["children"]
            )
            if (
                not _shape(activation, registry, maximum, family=330, duration=0)
                or tuple(activation["parameters"]) != (0, 0)
                or len(activation["children"]) != 1
                or not _shape(removal, registry, maximum, family=421, duration=0)
                or removal.get("children")
            ):
                return "hp_threshold_ordered_switch_unqualified"
            generic_id = activation["children"][0]
            leaf = compiled.effects[str(generic_id)]
            family = leaf["effect_class"]
            scalar_runner = registry["effects"].get(str(family), {})
            # These native families are fixed eWQ carriers, not resource payment.
            if (
                family not in (80, 120)
                or scalar_runner.get("runner") != "eWQ"
                or scalar_runner.get("dynamic_stat") is not False
                or type(scalar_runner.get("fixed_stat_id")) is not int
                or scalar_runner["fixed_stat_id"] in (1, 2, 3, 4)
                or tuple(carrier["native_effect_flags"])
                != ((1, 17) if family == 80 else (1,))
                or not _shape(leaf, registry, maximum, family=family, duration=-1)
                or leaf.get("children")
                or leaf.get("criteria", "").strip()
                or tuple(leaf["parameters"]) != (0, 1)
                or tuple(removal["parameters"]) != (generic_id, 0)
            ):
                return "hp_threshold_generic_scalar_identity_unqualified"
            matched = any(
                _criterion(
                    activation["criteria"],
                    generic_id,
                    threshold,
                    high=high,
                    removal=False,
                )
                and _criterion(
                    removal["criteria"], generic_id, threshold, high=high, removal=True
                )
                for high, threshold in ((True, 90), (False, 50), (False, 75))
            )
            if not matched:
                return "hp_threshold_complementary_predicates_unqualified"
        return None
    except (KeyError, TypeError, ValueError, IndexError, AttributeError, SyntaxError):
        return "hp_threshold_native_definition_incomplete"
