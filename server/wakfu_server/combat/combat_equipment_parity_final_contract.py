"""Permanent equipment damage carriers with parity-conditioned faq modifiers.

Only admission lives here. Existing source-runner events, live criteria and
native eZJ mutation own each attack's final modifier and effect publication.
"""
import ast
import math
from collections.abc import Mapping

from .combat_definitions import effect_profile, state_profile
from .combat_local_criteria import parse_local_criterion
from .combat_operation_registry import assess_operation


def _criterion(actual, expected):
    return ast.dump(parse_local_criterion(actual)) == ast.dump(
        parse_local_criterion(expected)
    )


def _trigger_predicate(expression):
    """Return the original event-axis/complement/state relation, or reject."""
    tree = parse_local_criterion(expression)
    body = tree.body if isinstance(tree, ast.Expression) else tree
    if (
        not isinstance(body, ast.BoolOp)
        or not isinstance(body.op, ast.And)
        or len(body.values) != 2
    ):
        raise ValueError("Missing native damage predicate")
    axis, excluded = body.values
    positive = not isinstance(axis, ast.UnaryOp)
    if not positive:
        if not isinstance(axis.op, ast.Not):
            raise ValueError("Unknown damage predicate polarity")
        axis = axis.operand
    if (
        not isinstance(axis, ast.Call)
        or not isinstance(axis.func, ast.Name)
        or axis.func.id not in ("IsTriggeredByMeleeEffect", "IsTriggeredByZoneEffect")
        or axis.args
        or axis.keywords
        or not isinstance(excluded, ast.UnaryOp)
        or not isinstance(excluded.op, ast.Not)
    ):
        raise ValueError("Unknown native damage predicate")
    call = excluded.operand
    if (
        not isinstance(call, ast.Call)
        or not isinstance(call.func, ast.Name)
        or call.func.id != "HasState"
        or len(call.args) != 2
        or call.keywords
        or not isinstance(call.args[0], ast.Constant)
        or type(call.args[0].value) is not int
        or not 0 < call.args[0].value <= 32767
        or not isinstance(call.args[1], ast.Constant)
        or call.args[1].value != "caster"
    ):
        raise ValueError("Missing native caster state exclusion")
    return axis.func.id, positive, call.args[0].value


def _shape(
    effect, registry, *, family, raw, selector, duration, root=False, damage=False
):
    timing = effect["native_timing_definition"]
    masks = effect["target_masks"]
    hmi = effect["native_hmi_actions"]
    if (
        any(
            type(effect[k]) is not int
            for k in (
                "effect_class",
                "parameter_count",
                "variant",
                "minimum_level",
                "maximum_level",
                "native_execution_mode",
            )
        )
        or effect["effect_class"] != family
        or effect["parameter_count"] * 2 != len(raw)
        or tuple(effect["parameters"]) != tuple(raw)
        or any(
            type(v) not in (int, float) or not math.isfinite(v)
            for v in effect["parameters"]
        )
        or effect["variant"] != 0
        or (effect["minimum_level"], effect["maximum_level"]) != (0, 32767)
        or effect["native_execution_mode"] != (0 if root else 2)
        or effect["native_definition_class"] != ("eVE" if root else "eVy")
        or effect["area_class"] != "anD"
        or effect["area_native"] != "point"
        or effect["native_target_selector"] != {"class": "fcE", "mask": selector}
        or type(effect["native_target_selector"].get("mask")) is not int
        or (root and effect.get("native_active_effect") is not False)
        or effect["native_localization_enabled"] is not False
        or tuple(effect["native_effect_flags"]) != ()
        or effect["application_flag"]
        != ("TRIGGERING_EFFECT_TARGET" if damage else "NONE")
        or effect["removal_flag"] != ("EFFECT_CARRIER" if damage else "NONE")
        or effect["probability_base"] != 100
        or effect["probability_per_level"] != 0
        or not isinstance(masks, (tuple, list))
        or len(masks) != 7
        or any(
            row is not None
            and (
                not isinstance(row, (tuple, list))
                or any(type(v) is not int for v in row)
            )
            for row in masks
        )
        or tuple(tuple(row) if row else None for row in masks)
        != (((2,),) + (None,) * 6 if damage else (None,) * 7)
        or not isinstance(hmi, Mapping)
        or set(hmi) != {"rzc", "rzd", "rze", "rzf", "rzg", "rzh"}
        or any(not isinstance(rows, (tuple, list)) or rows for rows in hmi.values())
        or assess_operation(effect, characteristic_registry=registry).status
        != "conditional"
    ):
        return False
    if root:
        return timing == {"clock_on_caster": False, "clock_on_target": True}
    return (
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
        and timing["clock_on_caster"] is False
        and timing["clock_on_target"] is True
        and timing["esr"] is False
        and timing["ryG"] is False
        and type(timing["ryE"]) is int
        and timing["ryE"] == duration
        and all(
            type(timing[k]) in (int, float) and timing[k] == 0
            for k in ("ryF", "ryH", "ryI")
        )
    )


def parity_final_state_contract(source, compiled, registry):
    """Qualify every root and branch without equipment/effect/state allowlists."""
    omitted = source.get("unplanned_passive_effect_ids")
    if (
        source.get("attachment_field") is not None
        or not isinstance(omitted, (tuple, list))
        or omitted
        or not source.get("roots")
    ):
        return "parity_final_complete_ordinary_source_required"
    effects, states = compiled.effects, compiled.source_states
    try:
        for identity in source["roots"]:
            root = effects[str(identity)]
            raw = root["parameters"]
            if (
                len(raw) != 6
                or tuple(raw[1:]) != (0, 1, 0, -1, 0)
                or root["criteria"].strip()
                or root["children"]
                or not _shape(
                    root,
                    registry,
                    family=304,
                    raw=raw,
                    selector=0,
                    duration=0,
                    root=True,
                )
            ):
                return "parity_final_permanent_self_root_required"
            state_id = effect_profile(
                root, source["native_retained_container"]["level"]
            )["parameters"][0]
            definition = states["states"][str(state_id)]
            profile = state_profile(states, state_id, 1)
            if (
                type(definition["maximum_level"]) is not int
                or definition["maximum_level"] != 1
                or len(definition["effect_ids"]) != 1
                or len(profile["effects"]) != 1
                or profile["duration"] != -1
                or profile["realtime_duration"] != 0
                or profile["clock_actor"] != "target"
                or profile["tick_at_turn_end"]
                or any(
                    profile[k]
                    for k in (
                        "additive",
                        "replace",
                        "refresh",
                        "protected",
                        "skip_turn_timer",
                    )
                )
            ):
                return "parity_final_permanent_carrier_required"
            carrier = effects[str(profile["effects"][0])]
            if (
                not _shape(
                    carrier,
                    registry,
                    family=330,
                    raw=(1, 0, 1, 0),
                    selector=1,
                    duration=-1,
                    damage=True,
                )
                or carrier["criteria"].strip()
                or len(carrier["children"]) != 2
            ):
                return "parity_final_source_damage_carrier_required"
            branches = []
            for child in carrier["children"]:
                branch = effects[str(child)]
                if (
                    not _shape(
                        branch, registry, family=330, raw=(), selector=0, duration=0
                    )
                    or len(branch["children"]) != 1
                ):
                    return "parity_final_complementary_branches_required"
                parity = next(
                    (
                        value
                        for value in (0, 1)
                        if _criterion(
                            branch["criteria"],
                            f"(GetFightCurrentTableTurn() % 2) == {value}",
                        )
                    ),
                    None,
                )
                if parity is None:
                    return "parity_final_native_table_turn_predicate_required"
                final = effects[str(branch["children"][0])]
                amount = effect_profile(final, 1)["parameters"]
                if (
                    len(amount) != 1
                    or type(amount[0]) is not int
                    or amount[0] <= 0
                    or not _shape(
                        final,
                        registry,
                        family=1093,
                        raw=(amount[0], 0),
                        selector=1,
                        duration=0,
                    )
                    or final["children"]
                ):
                    return "parity_final_instant_faq_modifier_required"
                branches.append(
                    (parity, *_trigger_predicate(final["criteria"]), amount[0])
                )
            even, odd = sorted(branches)
            if (
                even[0] != 0
                or odd[0] != 1
                or even[1] != odd[1]
                or even[2] == odd[2]
                or even[3:] != odd[3:]
            ):
                return "parity_final_complementary_trigger_relation_required"
    except (KeyError, TypeError, ValueError, IndexError):
        return "parity_final_native_graph_requires_qualification"
    return None
