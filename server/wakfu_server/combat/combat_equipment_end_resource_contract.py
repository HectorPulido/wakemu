"""Permanent SELF/end-boundary carriers granting timed maximum-only AP or MP.

Admission only. Live PA predicates, state presence, timer registration and exact
maximum-resource retirement remain owned by the existing native combat runners.
"""
import ast
import math
from collections.abc import Mapping

from .combat_definitions import effect_profile, state_profile
from .combat_local_criteria import parse_local_criterion
from .combat_operation_registry import assess_operation


def _predicate(expression, resource):
    """Accept a live resource threshold and optional native state exclusion."""
    try:
        tree = parse_local_criterion(expression)
    except ValueError:
        return False
    expected = parse_local_criterion(f'GetCharac("{resource}") >= 1')
    if ast.dump(tree) == ast.dump(expected):
        return True
    node = tree.body if isinstance(tree, ast.Expression) else tree
    if (
        not isinstance(node, ast.BoolOp)
        or not isinstance(node.op, ast.And)
        or len(node.values) != 2
    ):
        return False
    threshold = expected.body if isinstance(expected, ast.Expression) else expected
    first, second = node.values
    return (
        ast.dump(first) == ast.dump(threshold)
        and isinstance(second, ast.UnaryOp)
        and isinstance(second.op, ast.Not)
        and isinstance(second.operand, ast.Call)
        and isinstance(second.operand.func, ast.Name)
        and second.operand.func.id == "HasState"
        and len(second.operand.args) == 1
        and not second.operand.keywords
        and isinstance(second.operand.args[0], ast.Constant)
        and type(second.operand.args[0].value) is int
        and 0 < second.operand.args[0].value <= 32767
    )


def _shape(effect, registry, *, family, count, duration, root=False, events=()):
    if not isinstance(effect, Mapping):
        return False
    timing = effect.get("native_timing_definition", {})
    masks = effect.get("target_masks")
    hmi = effect.get("native_hmi_actions")
    raw = effect.get("parameters")
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
        and type(effect.get("parameter_count")) is int
        and effect.get("variant") == 0
        and type(effect.get("variant")) is int
        and effect.get("minimum_level") == 0
        and effect.get("maximum_level") == 32767
        and effect.get("native_execution_mode") == (0 if root else 2)
        and effect.get("native_definition_class") == ("eVE" if root else "eVy")
        and effect.get("native_target_selector") == {"class": "fcE", "mask": 1}
        and type(effect["native_target_selector"].get("mask")) is int
        and effect.get("area_native") == ("empty" if root else "point")
        and effect.get("area_class") == ("anA" if root else "anD")
        and effect.get("native_localization_enabled") is False
        and (not root or effect.get("native_active_effect") is False)
        and tuple(effect.get("native_effect_flags", ()))
        == (() if root or family == 330 else (17,))
        and isinstance(raw, (tuple, list))
        and len(raw) == count * 2
        and all(type(value) in (int, float) and math.isfinite(value) for value in raw)
        and isinstance(masks, (tuple, list))
        and len(masks) == 7
        and all(not masks[index] for index in (0, 1, 2, 3, 4, 6))
        and all(
            row is None
            or (
                isinstance(row, (tuple, list))
                and all(type(event) is int for event in row)
            )
            for row in masks
        )
        and tuple(masks[5] or ()) == events
        and isinstance(hmi, Mapping)
        and set(hmi) == {"rzc", "rzd", "rze", "rzf", "rzg", "rzh"}
        and all(isinstance(rows, (tuple, list)) and not rows for rows in hmi.values())
        and (
            timing == {"clock_on_caster": False, "clock_on_target": True}
            if root
            else (
                isinstance(timing, Mapping)
                and set(timing)
                == {
                    "clock_on_caster",
                    "clock_on_target",
                    "ryE",
                    "ryF",
                    "ryG",
                    "ryH",
                    "ryI",
                    "esr",
                }
                and timing.get("clock_on_caster") is False
                and timing.get("clock_on_target") is True
                and timing.get("ryE") == duration
                and type(timing.get("ryE")) is int
                and all(
                    type(timing.get(key)) in (int, float) and timing[key] == 0
                    for key in ("ryF", "ryH", "ryI")
                )
                and timing.get("ryG") is False
                and timing.get("esr") is (duration > 0)
            )
        )
        and effect.get("application_flag")
        == ("EFFECT_CARRIER" if family == 330 else "NONE")
        and effect.get("removal_flag")
        == ("EFFECT_CARRIER" if family == 330 else "NONE")
        and effect_profile(effect, 1)["probability"] == 100
        and effect.get("probability_per_level") == 0
        and assess_operation(effect, characteristic_registry=registry).status
        == "conditional"
    )


def end_resource_state_contract(source, compiled, registry):
    """Qualify the complete native carrier topology without item/state IDs."""
    omitted = source.get("unplanned_passive_effect_ids")
    if (
        source.get("attachment_field") is not None
        or not isinstance(omitted, (tuple, list))
        or omitted
    ):
        return "end_resource_complete_ordinary_source_required"
    roots = source.get("roots", ())
    if not roots:
        return "end_resource_state_root_required"
    effects, states = compiled.effects, compiled.source_states
    for reference in roots:
        root = effects.get(str(reference))
        if not _shape(root, registry, family=304, count=3, duration=0, root=True):
            return "end_resource_root_shape_requires_qualification"
        if root.get("criteria", "").strip() or root.get("children"):
            return "end_resource_root_predicate_requires_qualification"
        raw = root["parameters"]
        values = effect_profile(root, source["native_retained_container"]["level"])[
            "parameters"
        ]
        if any(raw[index] != 0 for index in (1, 3, 5)) or values[1:] != [1, -1]:
            return "end_resource_fixed_state_level_required"
        state_id = values[0]
        state = states["states"].get(str(state_id))
        if state is None or state.get("maximum_level") != 1:
            return "end_resource_state_domain_requires_qualification"
        profile = state_profile(states, state_id, 1)
        if (
            profile["duration"] != -1
            or profile["realtime_duration"] != 0
            or profile["clock_actor"] != "target"
            or profile["tick_at_turn_end"]
            or any(
                profile[key]
                for key in (
                    "additive",
                    "replace",
                    "refresh",
                    "protected",
                    "skip_turn_timer",
                )
            )
            or len(profile["effects"]) != 1
        ):
            return "end_resource_permanent_state_required"
        carrier = effects.get(str(profile["effects"][0]))
        if not _shape(
            carrier, registry, family=330, count=0, duration=-1, events=(1037,)
        ):
            return "end_resource_boundary_carrier_required"
        if len(carrier.get("children", ())) != 1:
            return "end_resource_single_resource_child_required"
        child = effects.get(str(carrier["children"][0]))
        family = None if child is None else child.get("effect_class")
        resource = {31: "AP", 41: "MP"}.get(family)
        if resource is None or not _shape(
            child, registry, family=family, count=3, duration=2
        ):
            return "end_resource_timed_resource_child_required"
        if child.get("criteria", "").strip() or child.get("children"):
            return "end_resource_plain_resource_child_required"
        if tuple(child["parameters"]) != (1, 0, 0, 0, 0, 0):
            return "end_resource_maximum_only_unit_gain_required"
        if not _predicate(carrier.get("criteria", ""), resource):
            return "end_resource_live_resource_predicate_required"
    return None
