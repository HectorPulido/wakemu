"""Complete permanent SELF carriers applying timed scalars above live HP threshold.

Admission only: existing native state, subscription, scalar and inverse runners
own values, current-characteristic mutation and exact one-turn retirement.
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
        == {304: 3, 330: 1, 100: 1, 39: 3, 1095: 1, 160: 1, 126: 1}[family]
        and (effect["minimum_level"], effect["maximum_level"]) == (0, 32767)
        and isinstance(raw, (tuple, list))
        and len(raw) == effect["parameter_count"] * 2
        and all(type(v) in (int, float) and math.isfinite(v) for v in raw)
        and effect["native_execution_mode"] == (0 if root else 2)
        and effect.get("native_definition_class") == ("eVE" if root else "eVy")
        and effect.get("native_target_selector")
        == {"class": "fcE", "mask": 1 if carrier or branch else 0}
        and type(effect["native_target_selector"].get("mask")) is int
        and effect.get("area_native") == ("empty" if family == 39 else "point")
        and effect.get("area_class") == ("anA" if family == 39 else "anD")
        and effect.get("native_localization_enabled") is False
        and (not root or effect.get("native_active_effect") is False)
        and tuple(effect.get("native_effect_flags", ()))
        == ((1, 17) if carrier else (17,) if branch else ())
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
                and timing["esr"] is (family == 39)
            )
        )
        and effect.get("probability_base") == 100
        and effect.get("probability_per_level") == 0
        and assess_operation(effect, characteristic_registry=registry).status
        == "conditional"
    )


def start_hp_scalar_state_contract(source, compiled, registry):
    """Admit only complete source-bound native start/HP/scalar topologies."""
    omitted = source.get("unplanned_passive_effect_ids")
    if (
        source.get("attachment_field") is not None
        or not isinstance(omitted, (tuple, list))
        or omitted
        or len(source.get("roots", ())) != 1
    ):
        return "start_hp_scalar_complete_single_source_required"
    try:
        level = source["native_retained_container"]["level"]
        reference = source["roots"][0]
        if (
            type(level) is not int
            or not 0 <= level <= 32767
            or type(reference) is not int
            or reference <= 0
        ):
            return "start_hp_scalar_source_identity_unqualified"
        root = compiled.effects[str(reference)]
        raw = root["parameters"]
        if (
            not _shape(root, registry, 304, role="root")
            or root.get("children")
            or root.get("criteria", "").strip()
            or tuple(raw)[1:] != (0, 1, 0, -1, 0)
        ):
            return "start_hp_scalar_initial_root_unqualified"
        state_id, applied, chance = effect_profile(root, level)["parameters"]
        if type(state_id) is not int or state_id <= 0 or applied != 1 or chance != -1:
            return "start_hp_scalar_initial_parameters_unqualified"
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
            or state["tick_at_turn_end"] is not False
            or any(
                state[k] is not False
                for k in (
                    "additive",
                    "replace",
                    "refresh",
                    "protected",
                    "skip_turn_timer",
                )
            )
            or len(state["effects"]) != 1
            or tuple(state["effects"]) != tuple(definition["effect_ids"])
            or tuple(state_profile(compiled.source_states, state_id, 0)["effects"])
            != tuple(state["effects"])
        ):
            return "start_hp_scalar_permanent_state_unqualified"
        carrier = compiled.effects[str(state["effects"][0])]
        if (
            not _shape(carrier, registry, 330, role="carrier")
            or tuple(carrier["parameters"]) != (0, 0)
            or carrier.get("criteria", "").strip()
            or len(carrier["children"]) != 1
        ):
            return "start_hp_scalar_start_subscription_unqualified"
        branch = compiled.effects[str(carrier["children"][0])]
        if (
            not _shape(branch, registry, 330, role="branch")
            or tuple(branch["parameters"]) != (0, 0)
            or ast.dump(parse_local_criterion(branch.get("criteria", "")))
            != ast.dump(parse_local_criterion('GetTotalHpInPercent("target") >= 80'))
        ):
            return "start_hp_scalar_live_hp_branch_unqualified"
        leaves = [compiled.effects[str(key)] for key in branch["children"]]
        families = tuple(row["effect_class"] for row in leaves)
        expected = {
            (100, 39, 1095): ((50, 0), (15, 0, 0, 0, 120, 0), (15, 0)),
            (100, 160): ((40, 0), (1, 0)),
            (100, 126): ((50, 0), (10, 0)),
        }.get(families)
        if expected is None or len(set(branch["children"])) != len(leaves):
            return "start_hp_scalar_complete_leaf_topology_unqualified"
        for effect, parameters in zip(leaves, expected):
            family = effect["effect_class"]
            if (
                not _shape(effect, registry, family, role="scalar")
                or tuple(effect["parameters"]) != parameters
                or effect.get("children")
                or effect.get("criteria", "").strip()
            ):
                return "start_hp_scalar_timed_leaf_unqualified"
            row = registry["effects"][str(family)]
            if (
                row.get("runner") != ("eWR" if family == 100 else "eWQ")
                or row.get("operation")
                != ("lose_current" if family == 100 else "gain_current")
                or row.get("limit_policy") != "NORMAL"
                or row.get("limit_policy_requires_owned_stack") is not False
            ):
                return "start_hp_scalar_native_operation_unqualified"
    except (KeyError, TypeError, ValueError, AttributeError):
        return "start_hp_scalar_incomplete_native_graph"
    return None
