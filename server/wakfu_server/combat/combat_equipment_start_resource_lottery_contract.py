"""Native one-success turn-start lottery granting or reducing timed maximum AP.

Admission only: the existing ordered-group, probability and resource runners
own draws, success counting, characteristic mutation and retained retirement.
"""
import ast
import math
from collections.abc import Mapping

from .combat_definitions import effect_profile, state_profile
from .combat_local_criteria import parse_local_criterion
from .combat_operation_registry import assess_operation


def _shape(effect, registry, family, *, role):
    if not isinstance(effect, Mapping):
        return False
    root = role == "root"
    carrier = role == "carrier"
    branch = role == "branch"
    raw = effect.get("parameters")
    masks = effect.get("target_masks")
    timing = effect.get("native_timing_definition")
    hmi = effect.get("native_hmi_actions")
    return (
        all(
            type(effect.get(k)) is int
            for k in (
                "effect_class",
                "variant",
                "parameter_count",
                "minimum_level",
                "maximum_level",
                "native_execution_mode",
            )
        )
        and effect["effect_class"] == family
        and effect["variant"] == 0
        and effect["parameter_count"]
        == (2 if carrier else {304: 3, 330: 1, 31: 3, 56: 1}[family])
        and (effect["minimum_level"], effect["maximum_level"]) == (0, 32767)
        and isinstance(raw, (tuple, list))
        and len(raw) == effect["parameter_count"] * 2
        and all(type(v) in (int, float) and math.isfinite(v) for v in raw)
        and effect["native_execution_mode"] == (0 if root else 2)
        and effect.get("native_definition_class") == ("eVE" if root else "eVy")
        and effect.get("native_target_selector")
        == {"class": "fcE", "mask": 0 if root else 1}
        and type(effect["native_target_selector"].get("mask")) is int
        and effect.get("area_native") == ("empty" if root else "point")
        and effect.get("area_class") == ("anA" if root else "anD")
        and effect.get("native_localization_enabled") is False
        and (not root or effect.get("native_active_effect") is False)
        and tuple(effect.get("native_effect_flags", ()))
        == (() if root or family == 56 else (17,))
        and effect.get("application_flag") == ("EFFECT_CARRIER" if carrier else "NONE")
        and effect.get("removal_flag") == ("EFFECT_CARRIER" if carrier else "NONE")
        and isinstance(masks, (tuple, list))
        and len(masks) == 7
        and all(
            row is None
            or (isinstance(row, (tuple, list)) and all(type(v) is int for v in row))
            for row in masks
        )
        and tuple(tuple(row) if row else None for row in masks)
        == ((None, None, None, None, None, (1001,), None) if carrier else (None,) * 7)
        and isinstance(hmi, Mapping)
        and set(hmi) == {"rzc", "rzd", "rze", "rzf", "rzg", "rzh"}
        and all(isinstance(row, (tuple, list)) and not row for row in hmi.values())
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
                and timing["clock_on_caster"] is False
                and timing["clock_on_target"] is True
                and type(timing["ryE"]) is int
                and timing["ryE"] == (-1 if carrier else 0 if branch else 1)
                and all(
                    type(timing[k]) in (int, float) and timing[k] == 0
                    for k in ("ryF", "ryH", "ryI")
                )
                and timing["ryG"] is False
                and timing["esr"] is (family in (31, 56))
            )
        )
        and effect.get("probability_base") == (50 if branch else 100)
        and effect.get("probability_per_level") == 0
        and assess_operation(effect, characteristic_registry=registry).status
        == "conditional"
    )


def start_resource_lottery_contract(source, compiled, registry):
    """Qualify the complete original one-success resource lottery topology."""
    omitted = source.get("unplanned_passive_effect_ids")
    if (
        source.get("attachment_field") is not None
        or not isinstance(omitted, (tuple, list))
        or omitted
        or len(source.get("roots", ())) != 1
    ):
        return "start_resource_lottery_complete_single_source_required"
    try:
        level = source["native_retained_container"]["level"]
        reference = source["roots"][0]
        if (
            type(level) is not int
            or not 0 <= level <= 32767
            or type(reference) is not int
            or reference <= 0
        ):
            return "start_resource_lottery_source_identity_unqualified"
        root = compiled.effects[str(reference)]
        if (
            not _shape(root, registry, 304, role="root")
            or root.get("children")
            or root.get("criteria", "").strip()
            or tuple(root["parameters"])[1:] != (0, 1, 0, -1, 0)
        ):
            return "start_resource_lottery_initial_root_unqualified"
        state_id, applied, chance = effect_profile(root, level)["parameters"]
        if type(state_id) is not int or state_id <= 0 or applied != 1 or chance != -1:
            return "start_resource_lottery_initial_parameters_unqualified"
        definition = compiled.source_states["states"][str(state_id)]
        state = state_profile(compiled.source_states, state_id, 1)
        if (
            type(definition["maximum_level"]) is not int
            or definition["maximum_level"] != 1
            or definition["duration_per_level"] != 0
            or definition["realtime_duration_per_level"] != 0
            or state["duration"] != -1
            or state["realtime_duration"] != 0
            or state["clock_actor"] != "target"
            or state["tick_at_turn_end"] is not True
            or state["replace"] is not True
            or any(
                state[k] is not False
                for k in ("additive", "refresh", "protected", "skip_turn_timer")
            )
            or len(state["effects"]) != 1
            or tuple(state["effects"]) != tuple(definition["effect_ids"])
            or tuple(state_profile(compiled.source_states, state_id, 0)["effects"])
            != tuple(state["effects"])
        ):
            return "start_resource_lottery_permanent_state_unqualified"
        carrier = compiled.effects[str(state["effects"][0])]
        expected = (
            'not HasEffectWithActionId("target", 933) and '
            'not HasEffectWithActionId("target", 982) and '
            "GetFightModel() <> 67 and GetFightModel() <> 68"
        )
        if (
            not _shape(carrier, registry, 330, role="carrier")
            or tuple(carrier["parameters"]) != (1, 0, 1, 0)
            or ast.dump(parse_local_criterion(carrier.get("criteria", "")))
            != ast.dump(parse_local_criterion(expected))
            or len(carrier["children"]) != 2
            or len(set(carrier["children"])) != 2
        ):
            return "start_resource_lottery_single_success_subscription_unqualified"
        branch, loss = (compiled.effects[str(key)] for key in carrier["children"])
        if (
            not _shape(branch, registry, 330, role="branch")
            or tuple(branch["parameters"]) != (0, 0)
            or branch.get("criteria", "").strip()
            or len(branch["children"]) != 1
        ):
            return "start_resource_lottery_chance_branch_unqualified"
        gain = compiled.effects[str(branch["children"][0])]
        if (
            not _shape(gain, registry, 31, role="gain")
            or tuple(gain["parameters"]) != (1, 0, 1, 0, 0, 0)
            or gain.get("criteria", "").strip()
            or gain.get("children")
            or not _shape(loss, registry, 56, role="loss")
            or tuple(loss["parameters"]) != (1, 0)
            or loss.get("criteria", "").strip()
            or loss.get("children")
        ):
            return "start_resource_lottery_timed_ap_pair_unqualified"
    except (KeyError, TypeError, ValueError, AttributeError):
        return "start_resource_lottery_incomplete_native_graph"
    return None
