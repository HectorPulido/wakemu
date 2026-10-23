"""Complete native equipment carriers healing below HP thresholds at turn start.

Admission only. Existing live HP criteria, ordered subscriptions, native healing
and retained inverses remain responsible for execution and removal.
"""
import ast
import math
from collections.abc import Mapping

from .combat_definitions import effect_profile, state_profile
from .combat_local_criteria import parse_local_criterion
from .combat_operation_registry import assess_operation


def _shape(effect, registry, family, *, root=False):
    if not isinstance(effect, Mapping):
        return False
    carrier = family == 330
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
        and effect["parameter_count"] == {304: 3, 330: 1, 400: 1, 25: 2}[family]
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
        == (() if root else (1, 17) if carrier else (17,))
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
                and timing["ryE"] == (0 if family == 25 else -1)
                and all(
                    type(timing[k]) in (int, float) and timing[k] == 0
                    for k in ("ryF", "ryH", "ryI")
                )
                and timing["ryG"] is False
                and timing["esr"] is (family == 25)
            )
        )
        and effect.get("probability_base") == 100
        and effect.get("probability_per_level") == 0
        and assess_operation(effect, characteristic_registry=registry).status
        == "conditional"
    )


def start_heal_state_contract(source, compiled, registry):
    """Qualify full native ordered carriers; never project or execute a heal."""
    omitted = source.get("unplanned_passive_effect_ids")
    roots = source.get("roots", ())
    if (
        source.get("attachment_field") is not None
        or not isinstance(omitted, (tuple, list))
        or omitted
        or len(roots) not in (2, 3)
        or len(set(roots)) != len(roots)
    ):
        return "start_heal_complete_ordinary_source_required"
    try:
        level = source["native_retained_container"]["level"]
        if type(level) is not int or not 0 <= level <= 32767:
            return "start_heal_source_level_unqualified"
        thresholds = []
        identities = set()
        for reference in roots:
            if type(reference) is not int or reference <= 0:
                return "start_heal_root_identity_unqualified"
            root = compiled.effects[str(reference)]
            if (
                not _shape(root, registry, 304, root=True)
                or root.get("children")
                or root.get("criteria", "").strip()
                or tuple(root["parameters"])[1::2] != (0, 0, 0)
            ):
                return "start_heal_initial_root_unqualified"
            state_id, applied, chance = effect_profile(root, level)["parameters"]
            if (
                type(state_id) is not int
                or state_id <= 0
                or state_id in identities
                or type(applied) is not int
                or not 0 < applied <= 100
                or chance != -1
            ):
                return "start_heal_initial_parameters_unqualified"
            identities.add(state_id)
            definition = compiled.source_states["states"][str(state_id)]
            state = state_profile(compiled.source_states, state_id, applied)
            if (
                definition["maximum_level"] != 100
                or definition["duration_per_level"] != 0
                or definition["realtime_duration_per_level"] != 0
                or state["duration"] != -1
                or state["realtime_duration"] != 0
                or state["clock_actor"] != "target"
                or state["tick_at_turn_end"] is not False
                or state["additive"] is not True
                or state["replace"] is not False
                or state["refresh"] is not False
                or state["protected"] is not False
                or state["skip_turn_timer"] is not False
                or len(state["effects"]) != 2
                or tuple(state["effects"]) != tuple(definition["effect_ids"])
            ):
                return "start_heal_state_clock_or_stack_unqualified"
            for requested in (0, 100):
                if tuple(
                    state_profile(compiled.source_states, state_id, requested)[
                        "effects"
                    ]
                ) != tuple(state["effects"]):
                    return "start_heal_state_level_branch_unqualified"
            marker, carrier = (compiled.effects[str(key)] for key in state["effects"])
            if (
                not _shape(marker, registry, 400)
                or marker.get("children")
                or marker.get("criteria", "").strip()
                or not _shape(carrier, registry, 330)
                or carrier.get("criteria", "").strip()
                or tuple(carrier["parameters"]) != (0, 0)
                or len(carrier["children"]) != 1
            ):
                return "start_heal_subscription_or_marker_unqualified"
            heal = compiled.effects[str(carrier["children"][0])]
            if (
                not _shape(heal, registry, 25)
                or heal.get("children")
                or tuple(heal["parameters"])[2:] != (2, 0)
                or tuple(heal["parameters"])[:2] != tuple(marker["parameters"])
                or tuple(marker["parameters"]) not in ((0, 25), (0, 40))
            ):
                return "start_heal_native_healing_parameters_unqualified"
            matches = [
                threshold
                for threshold in (25, 33, 50, 66, 75)
                if ast.dump(parse_local_criterion(heal.get("criteria", "")))
                == ast.dump(
                    parse_local_criterion(
                        f'GetTotalHpInPercent("target") <= {threshold}'
                    )
                )
            ]
            if len(matches) != 1:
                return "start_heal_live_hp_predicate_unqualified"
            thresholds.extend(matches)
        if tuple(sorted(thresholds)) not in ((33, 66), (25, 50, 75)):
            return "start_heal_complete_threshold_set_unqualified"
    except (KeyError, TypeError, ValueError, AttributeError):
        return "start_heal_incomplete_native_graph"
    return None
