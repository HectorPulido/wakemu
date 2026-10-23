"""Finite ordinary movement/cast/elemental triggering-runner graph admission.

This qualifies definitions only. Existing1005/1024/1025 producers, native
subscription rebinding, scoped eZL430 mutation and eXe421 removal own execution.
No item/state/effect identity or damage result is synthesized here.
"""
import ast
import math
from collections.abc import Mapping

from .combat_definitions import effect_profile, state_profile
from .combat_local_criteria import parse_local_criterion
from .combat_operation_registry import assess_operation

_HMI = frozenset(("rzc", "rzd", "rze", "rzf", "rzg", "rzh"))
_CLOCK = frozenset(
    ("clock_on_caster", "clock_on_target", "ryE", "ryF", "ryG", "ryH", "ryI", "esr")
)


def _criterion(actual, expected):
    if type(actual) is not str:
        return False
    if not expected:
        return not actual.strip()
    return ast.dump(parse_local_criterion(actual)) == ast.dump(
        parse_local_criterion(expected)
    )


def _shape(
    effect,
    registry,
    *,
    family,
    parameters=(),
    duration=0,
    selector=1,
    masks=(None,) * 7,
    application="NONE",
    removal="NONE",
    caster_clock=False,
    at_end=False,
    criterion="",
    root=False,
):
    timing = effect["native_timing_definition"]
    hmi = effect["native_hmi_actions"]
    actual_masks = effect["target_masks"]
    raw = effect["parameters"]
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
        or effect["variant"] != 0
        or effect["parameter_count"] * 2 != len(parameters)
        or not isinstance(raw, (tuple, list))
        or tuple(raw) != parameters
        or any(type(v) not in (int, float) or not math.isfinite(v) for v in raw)
        or (effect["minimum_level"], effect["maximum_level"]) != (0, 32767)
        or effect["native_execution_mode"] != (0 if root else 2)
        or effect["native_definition_class"] != ("eVE" if root else "eVy")
        or effect["area_class"] != ("anA" if root else "anD")
        or effect["area_native"] != ("empty" if root else "point")
        or effect["native_target_selector"] != {"class": "fcE", "mask": selector}
        or type(effect["native_target_selector"].get("mask")) is not int
        or (root and effect.get("native_active_effect") is not False)
        or effect["native_localization_enabled"] is not False
        or tuple(effect["native_effect_flags"]) != (() if root else (17,))
        or effect["application_flag"] != application
        or effect["removal_flag"] != removal
        or effect["probability_base"] != 100
        or effect["probability_per_level"] != 0
        or not isinstance(actual_masks, (tuple, list))
        or len(actual_masks) != 7
        or any(
            row is not None
            and (
                not isinstance(row, (tuple, list))
                or any(type(v) is not int for v in row)
            )
            for row in actual_masks
        )
        or tuple(tuple(row) if row else None for row in actual_masks) != masks
        or not isinstance(hmi, Mapping)
        or set(hmi) != _HMI
        or any(not isinstance(rows, (tuple, list)) or rows for rows in hmi.values())
        or not _criterion(effect["criteria"], criterion)
    ):
        return False
    if root:
        clock_ok = timing == {"clock_on_caster": False, "clock_on_target": True}
    else:
        clock_ok = (
            isinstance(timing, Mapping)
            and set(timing) == _CLOCK
            and timing["clock_on_caster"] is caster_clock
            and timing["clock_on_target"] is (not caster_clock)
            and timing["esr"] is at_end
            and timing["ryG"] is False
            and type(timing["ryE"]) is int
            and timing["ryE"] == duration
            and all(
                type(timing[k]) in (int, float) and timing[k] == 0
                for k in ("ryF", "ryH", "ryI")
            )
        )
    if not clock_ok:
        return False
    if family == 430:
        # The generic operation description alone is not accreditation.
        # Admission stays limited to reviewed eZL mode1 signed addition,
        # with no replace, timing, subscription, child or auxiliary mode. The
        # real handler still requires an authoritative live triggering Qe.
        return (
            len(parameters) == 6
            and parameters[0:2] == (1, 0)
            and type(parameters[2]) is int
            and -(1 << 31) < parameters[2] < (1 << 31)
            and parameters[2] != 0
            and parameters[3:] == (0, 0, 0)
            and not effect["children"]
            and duration == 0
            and not root
            and selector == 1
            and masks == (None,) * 7
            and application == removal == "NONE"
            and not caster_clock
            and not at_end
            and assess_operation(effect, characteristic_registry=registry).status
            == "conditional"
        )
    return (
        assess_operation(effect, characteristic_registry=registry).status
        == "conditional"
    )


def reactive_trigger_state_contract(source, compiled, registry):
    """Return None only for the complete source-derived four-element topology."""
    try:
        roots = source["roots"]
        level = source["native_retained_container"]["level"]
        omitted = source.get("unplanned_passive_effect_ids")
        if (
            source.get("attachment_field") is not None
            or len(roots) != 1
            or type(level) is not int
            or not 0 <= level <= 32767
            or not isinstance(omitted, (tuple, list))
            or omitted
        ):
            return "reactive_trigger_ordinary_source_unqualified"
        effects, seen = compiled.effects, set()

        def node(identity, family, **shape):
            if type(identity) is not int or identity <= 0 or identity in seen:
                raise ValueError("Duplicate or invalid graph node")
            effect = effects[str(identity)]
            if not _shape(effect, registry, family=family, **shape):
                raise ValueError(f"Unqualified native{family} graph node")
            seen.add(identity)
            return effect

        root = effects[str(roots[0])]
        values = effect_profile(root, level)["parameters"]
        if len(values) != 3 or values[0] <= 0 or values[1:] != [1, -1]:
            return "reactive_trigger_initial_state_parameters_unqualified"
        state_id = values[0]
        root = node(
            roots[0], 304, parameters=(state_id, 0, 1, 0, -1, 0), root=True, selector=0
        )
        if root["children"]:
            return "reactive_trigger_initial_children_unqualified"
        state = compiled.source_states["states"][str(state_id)]
        members = tuple(state["effect_ids"])
        if (
            type(state["maximum_level"]) is not int
            or state["maximum_level"] != 1
            or len(members) != 1
            or state["duration_per_level"] != 0
            or state["realtime_duration_per_level"] != 0
        ):
            return "reactive_trigger_permanent_state_unqualified"
        for rank in (0, 1):
            profile = state_profile(compiled.source_states, state_id, rank)
            if (
                tuple(profile["effects"]) != members
                or profile["duration"] != -1
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
                return "reactive_trigger_permanent_clock_unqualified"
        movement = node(
            members[0],
            330,
            duration=-1,
            masks=(None, None, None, None, None, (1005,), None),
            application="EFFECT_CARRIER",
            removal="EFFECT_CARRIER",
        )
        children = movement["children"]
        if len(children) != 9 or len(set(children)) != 9:
            return "reactive_trigger_movement_topology_unqualified"
        markers, negative_groups, cast_id = (
            tuple(children[:4]),
            tuple(children[4:8]),
            children[8],
        )
        for identity in markers:
            marker = node(identity, 400, duration=1)
            if marker["children"]:
                return "reactive_trigger_marker_children_unqualified"
        cast = node(
            cast_id,
            330,
            duration=1,
            masks=(None, None, None, None, None, (1024,), None),
            application="EFFECT_CARRIER",
            removal="EFFECT_CARRIER",
        )
        if len(cast["children"]) != 4 or len(set(cast["children"])) != 4:
            return "reactive_trigger_cast_topology_unqualified"
        magnitude = None
        for event, marker_id, negative_id, positive_id in zip(
            (5, 6, 8, 7), markers, negative_groups, cast["children"]
        ):
            negative = node(
                negative_id,
                330,
                duration=1,
                caster_clock=True,
                masks=(None, (event,), None, None, None, None, None),
                application="EFFECT_CARRIER",
                removal="EFFECT_CARRIER",
            )
            if len(negative["children"]) != 2:
                return "reactive_trigger_negative_topology_unqualified"
            modifier_id, removal_id = negative["children"]
            modifier = effects[str(modifier_id)]
            params = tuple(modifier["parameters"])
            if (
                len(params) != 6
                or params[2] != int(params[2])
                or not -(1 << 31) < params[2] < 0
            ):
                return "reactive_trigger_signed_amount_unqualified"
            amount = -int(params[2])
            if magnitude is not None and amount != magnitude:
                return "reactive_trigger_element_amount_mismatch"
            magnitude = amount
            node(modifier_id, 430, parameters=(1, 0, -amount, 0, 0, 0))
            removed = node(removal_id, 421, parameters=(marker_id, 0), selector=8194)
            if removed["children"]:
                return "reactive_trigger_remove_children_unqualified"
            positive = node(
                positive_id,
                330,
                duration=1,
                masks=(None, (event,), (1025,), None, None, None, None),
                application="TRIGGERING_EFFECT_TARGET",
                removal="EFFECT_CARRIER",
                criterion=f'HasEffectWithSpecificId("caster", {marker_id})',
            )
            if len(positive["children"]) != 3:
                return "reactive_trigger_positive_topology_unqualified"
            gain_id, once_id, cleanup_id = positive["children"]
            node(
                gain_id,
                430,
                parameters=(1, 0, amount, 0, 0, 0),
                criterion=f'not HasEffectWithSpecificId("target", {once_id})',
            )
            once = node(
                once_id,
                400,
                duration=1,
                masks=(None, None, (1025,), None, None, None, None),
            )
            if once["children"]:
                return "reactive_trigger_once_marker_children_unqualified"
            cleanup = node(
                cleanup_id,
                330,
                duration=1,
                at_end=True,
                selector=8194,
                masks=(None, None, None, None, None, (1025,), None),
                application="EFFECT_CASTER",
                removal="EFFECT_ORIGINAL_CASTER",
            )
            if len(cleanup["children"]) != 2:
                return "reactive_trigger_cleanup_topology_unqualified"
            for identity, target in zip(cleanup["children"], (negative_id, marker_id)):
                removed = node(identity, 421, parameters=(target, 0), selector=0)
                if removed["children"]:
                    return "reactive_trigger_cleanup_children_unqualified"
        return None if len(seen) == 43 else "reactive_trigger_incomplete_graph"
    except (KeyError, TypeError, ValueError, IndexError, OverflowError):
        return "reactive_trigger_incomplete_or_unknown_definition"
