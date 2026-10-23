"""Owned direct eXE markers retain original visual and criterion lifecycles.

No characteristic is granted here. Qualified roots still execute through the
native null runner, retaining the original PL, definition, HMI and removal UID.
"""
import ast
import math
from .combat_local_criteria import parse_local_criterion

_PHASES = frozenset(("rzc", "rzd", "rze", "rzf", "rzg", "rzh"))


def _criterion(text):
    if type(text) is not str:
        return False
    if not text.strip():
        return True
    try:
        node = parse_local_criterion(text)
    except ValueError:
        return False

    def known(node):
        if isinstance(node, ast.BoolOp) and isinstance(node.op, (ast.And, ast.Or)):
            return all(known(child) for child in node.values)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            return known(node.operand)
        if isinstance(node, ast.Call):
            return (
                isinstance(node.func, ast.Name)
                and node.func.id == "IsDay"
                and not node.args
                and not node.keywords
            )
        return (
            isinstance(node, ast.Compare)
            and len(node.ops) == 1
            and isinstance(node.ops[0], ast.Eq)
            and len(node.comparators) == 1
            and isinstance(node.left, ast.Call)
            and isinstance(node.left.func, ast.Name)
            and node.left.func.id == "GetInstanceId"
            and not node.left.args
            and not node.left.keywords
            and isinstance(node.comparators[0], ast.Constant)
            and type(node.comparators[0].value) is int
            and 0 <= node.comparators[0].value < (1 << 31)
        )

    return known(node)


def _metadata(effect):
    """Shared reviewed ordinary eVE metadata; operation semantics stay below."""
    if not isinstance(effect, dict):
        return False
    if (
        effect.get("variant") != 0
        or effect.get("minimum_level") != 0
        or effect.get("maximum_level") != 32767
        or effect.get("native_active_effect") is not False
        or effect.get("native_definition_class") != "eVE"
        or effect.get("native_execution_mode") != 0
        or effect.get("native_localization_enabled") is not False
        or effect.get("children") not in ([], ())
        or effect.get("application_flag") != "NONE"
        or effect.get("removal_flag") != "NONE"
        or effect.get("probability_base") != 100
        or effect.get("probability_per_level") != 0
        or tuple(effect.get("native_effect_flags", ())) != ()
        or effect.get("native_timing_definition")
        != {"clock_on_caster": False, "clock_on_target": True}
        or (effect.get("area_native"), effect.get("area_class"))
        not in (("empty", "anA"), ("point", "anD"))
        or not _criterion(effect.get("criteria"))
    ):
        return False
    masks, selector = effect.get("target_masks"), effect.get("native_target_selector")
    if (
        not isinstance(masks, (tuple, list))
        or len(masks) != 7
        or any(masks)
        or not isinstance(selector, dict)
        or selector.get("class") != "fcE"
    ):
        return False
    actions = effect.get("native_hmi_actions")
    if (
        not isinstance(actions, dict)
        or set(actions) != _PHASES
        or any(not isinstance(rows, (tuple, list)) for rows in actions.values())
    ):
        return False
    return True


def direct_marker_effect(effect):
    """Qualify a complete original compiled direct400 definition, not its ID."""
    if not _metadata(effect) or effect.get("effect_class") != 400:
        return False
    actions = effect["native_hmi_actions"]
    selector = effect["native_target_selector"]
    parameters = effect.get("parameters")
    if not isinstance(parameters, (tuple, list)):
        return False
    if not any(actions.values()):
        # Original eXE.C reads parameter0 at level0 and narrows to a status byte.
        return not effect["criteria"].strip() and (
            effect.get("parameter_count") == 1
            and tuple(parameters) == (0, 0)
            and selector.get("mask") == 0
            or effect.get("parameter_count") == 0
            and not parameters
            and selector.get("mask") == 16
            and (effect["area_native"], effect["area_class"]) == ("point", "anD")
        )
    if (
        effect.get("parameter_count") != 0
        or parameters
        or selector.get("mask") not in (1, 2)
    ):
        return False
    if actions["rzd"] or actions["rzg"] or bool(actions["rzc"]) == bool(actions["rze"]):
        return False
    installed = actions["rzc"] or actions["rze"]
    if installed != actions["rzf"] or installed != actions["rzh"]:
        return False
    return all(
        isinstance(row, dict)
        and set(row) == {"id", "type", "native", "aYc", "aYd"}
        and type(row["id"]) is int
        and row["id"] > 0
        and row["type"] in ("LIGHT_SOURCE", "PARTICLE_SYSTEM")
        and isinstance(row["native"], str)
        and bool(row["native"])
        and row["aYc"] is False
        and row["aYd"] is False
        for row in installed
    )


def direct_world_property_effect(effect):
    """Original eWw FORCE_4_DIRECTION root; keep real property ownership."""
    if (
        not _metadata(effect)
        or effect.get("effect_class") != 449
        or effect.get("parameter_count") != 1
        or effect["criteria"].strip()
        or any(effect["native_hmi_actions"].values())
    ):
        return False
    parameters = effect.get("parameters")
    if (
        not isinstance(parameters, (tuple, list))
        or len(parameters) != 2
        or type(parameters[0]) not in (int, float)
        or not math.isfinite(parameters[0])
        or parameters[0] != int(parameters[0])
        or parameters[1] != 0
        or effect["native_target_selector"].get("mask") != 1
    ):
        return False
    from .combat_world_properties import registry

    row = registry().get(str(int(parameters[0])))
    return (
        isinstance(row, dict)
        and row.get("name") == "FORCE_4_DIRECTION"
        and row.get("fight_property") == -1
    )


def direct_owned_effect(effect):
    return direct_marker_effect(effect) or direct_world_property_effect(effect)


def direct_marker_root(root):
    """Use the existing native definition compiler for planner/static admission."""
    from .combat_copied_equipment_execution import equipment_effect_definitions

    try:
        compiled = equipment_effect_definitions({"roots": [root]})
        return direct_owned_effect(compiled[str(root["reference"])])
    except (ValueError, TypeError, KeyError):
        return False


def direct_marker_contract(source, compiled, registry):
    if source.get("attachment_field") is not None or not source.get("roots"):
        return "direct_marker_requires_owned_ordinary_roots"
    container = source.get("native_retained_container", {})
    if (
        container.get("present") is not True
        or container.get("type") != 12
        or type(container.get("level")) is not int
        or not 0 <= container["level"] <= 32767
    ):
        return "direct_marker_requires_native_item_container"
    if registry.get("effects", {}).get("400", {}).get("runner") != "eXE":
        return "direct_marker_requires_native_null_runner"
    for reference in source["roots"]:
        if not direct_owned_effect(compiled.effects.get(str(reference))):
            return "direct_marker_unqualified_definition"
    return None
