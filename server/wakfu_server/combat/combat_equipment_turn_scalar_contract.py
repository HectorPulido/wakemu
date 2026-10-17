"""Finite permanent carrier -> own-turn parity -> timed MP maximum contract.

This admits definitions to existing native runners; it pays no resources and
does not calculate, apply or expire a characteristic itself. Item/state/effect
identities are derived from the source, never an item-specific allowlist.
"""
import ast
from collections.abc import Mapping

from .combat_definitions import effect_profile, state_profile
from .combat_local_criteria import parse_local_criterion
from .combat_operation_registry import assess_operation


def _parity(expression):
    tree = parse_local_criterion(expression)
    if isinstance(tree, ast.Expression):
        tree = tree.body
    return (
        isinstance(tree, ast.Compare)
        and len(tree.ops) == len(tree.comparators) == 1
        and isinstance(tree.ops[0], ast.Eq)
        and isinstance(tree.comparators[0], ast.Constant)
        and type(tree.comparators[0].value) is int
        and tree.comparators[0].value == 0
        and isinstance(tree.left, ast.BinOp)
        and isinstance(tree.left.op, ast.Mod)
        and isinstance(tree.left.right, ast.Constant)
        and type(tree.left.right.value) is int
        and tree.left.right.value == 2
        and isinstance(tree.left.left, ast.Call)
        and isinstance(tree.left.left.func, ast.Name)
        and tree.left.left.func.id == "GetFightCurrentTableTurn"
        and not tree.left.left.args
        and not tree.left.left.keywords
    )


def _common(effect, registry, *, mask, area, events, flags, application, removal):
    selector = effect.get("native_target_selector", {})
    masks = effect.get("target_masks")
    return (
        type(effect.get("variant")) is int
        and effect["variant"] == 0
        and isinstance(selector, Mapping)
        and type(selector.get("mask")) is int
        and effect.get("native_definition_class")
        == ("eVE" if area == "empty" else "eVy")
        and effect.get("native_execution_mode") == (0 if area == "empty" else 2)
        and selector.get("class") == "fcE"
        and selector.get("mask") == mask
        and effect.get("area_native") == area
        and masks is not None
        and len(masks) == 7
        and all(not masks[index] for index in (0, 1, 2, 3, 4, 6))
        and tuple(masks[5] or ()) == events
        and tuple(effect.get("native_effect_flags", ())) == flags
        and effect.get("application_flag") == application
        and effect.get("removal_flag") == removal
        and assess_operation(effect, characteristic_registry=registry).status
        == "conditional"
    )


def _timing(effect, duration):
    row = effect.get("native_timing_definition", {})
    return (
        isinstance(row, Mapping)
        and row.get("esr") is True
        and type(row.get("ryE")) is int
        and row["ryE"] == duration
        and row.get("ryF") == 0
        and row.get("ryG") is False
        and row.get("ryH") == row.get("ryI") == 0
        and row.get("clock_on_caster") is False
        and row.get("clock_on_target") is True
    )


def turn_scalar_state_contract(source, compiled, registry):
    """Return None only for the complete finite parity/timed-MP topology."""
    if source.get("attachment_field") is not None or len(source.get("roots", ())) != 1:
        return "turn_scalar_requires_one_ordinary_state_root"
    try:
        root = compiled.effects[str(source["roots"][0])]
        level = source["native_retained_container"]["level"]
        values = effect_profile(root, level)
        if (
            root["effect_class"] != 304
            or root.get("children")
            or root.get("criteria", "").strip()
            or values["probability"] != 100
            or not root["minimum_level"] <= level <= root["maximum_level"]
            or not _common(
                root,
                registry,
                mask=0,
                area="empty",
                events=(),
                flags=(),
                application="NONE",
                removal="NONE",
            )
            or dict(root.get("native_timing_definition", {}))
            != {"clock_on_caster": False, "clock_on_target": True}
            or len(root["parameters"]) != 6
            or tuple(root["parameters"][1:]) != (0, 1, 0, -1, 0)
        ):
            return "turn_scalar_initial_state_contract_unqualified"
        state_id, applied_level, chance = values["parameters"]
        if applied_level != 1 or chance != -1:
            return "turn_scalar_initial_state_parameters_unqualified"
        definition = compiled.source_states["states"][str(state_id)]
        if definition["maximum_level"] != 1:
            return "turn_scalar_state_domain_unqualified"
        state_effects = None
        for requested in (0, 1):
            state = state_profile(compiled.source_states, state_id, requested)
            if (
                state["duration"] != -1
                or state["realtime_duration"] != 0
                or state["clock_actor"] != "target"
                or state["tick_at_turn_end"] is not True
                or state["replace"] is not True
                or state["refresh"] is not False
                or state["additive"] is not False
                or state["protected"] is not False
                or state["skip_turn_timer"] is not False
                or len(state["effects"]) != 1
            ):
                return "turn_scalar_permanent_state_clock_unqualified"
            if state_effects is not None and state_effects != state["effects"]:
                return "turn_scalar_state_level_branch_unqualified"
            state_effects = state["effects"]
        group = compiled.effects[str(state_effects[0])]
        if (
            group["effect_class"] != 330
            or group.get("criteria", "").strip()
            or tuple(group["parameters"]) != (0, 0)
            or len(group["children"]) != 1
            or not group["minimum_level"] <= 0 <= 1 <= group["maximum_level"]
            or not _common(
                group,
                registry,
                mask=0,
                area="point",
                events=(1001,),
                flags=(17,),
                application="EFFECT_CARRIER",
                removal="EFFECT_CARRIER",
            )
            or not _timing(group, -1)
            or any(effect_profile(group, rank)["probability"] != 100 for rank in (0, 1))
        ):
            return "turn_scalar_own_turn_carrier_unqualified"
        child = compiled.effects[str(group["children"][0])]
        raw = child["parameters"]
        if (
            child["effect_class"] != 41
            or child.get("children")
            or not child["minimum_level"] <= 0 <= 1 <= child["maximum_level"]
            or not _common(
                child,
                registry,
                mask=1,
                area="point",
                events=(),
                flags=(17,),
                application="NONE",
                removal="NONE",
            )
            or not _timing(child, 1)
            or not _parity(child["criteria"])
            or len(raw) != 6
            or type(raw[0]) not in (int, float)
            or raw[0] <= 0
            or int(raw[0]) != raw[0]
            or tuple(raw[1:]) != (0, 1, 0, 0, 0)
            or any(effect_profile(child, rank)["probability"] != 100 for rank in (0, 1))
        ):
            return "turn_scalar_timed_mp_parity_unqualified"
        return None
    except (KeyError, TypeError, ValueError, IndexError):
        return "turn_scalar_native_definition_incomplete"
