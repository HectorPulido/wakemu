"""Select original retained transformation HMIs without gameplay execution."""
import ast

POLICY = "original-retained-hmi-appearance-v1"
HMI_TYPES = frozenset(
    (
        "APPEARANCE_CHANGE",
        "SKIN_COLOR_CHANGE",
        "SKIN_PART_VISIBILITY",
        "PARTICLE_SYSTEM",
    )
)
VISUAL_TYPES = HMI_TYPES - {"PARTICLE_SYSTEM"}
PHASES = frozenset(("rzc", "rzd", "rze", "rzf", "rzg", "rzh"))


def select(character, state):
    """Return exact applicable nodes in original state-root execution order.

    Native appearance modifiers restore their underlying live model on removal.
    This function does not write persistent appearance or reconstruct actors.
    """
    metadata = state.get("metadata", {})
    identities = metadata.get("native_visual_effect_ids", ())
    if not identities:
        return ()
    if (
        metadata.get("native_visual_policy") != POLICY
        or not isinstance(identities, (list, tuple))
        or any(type(identity) is not int or identity <= 0 for identity in identities)
        or len(set(identities)) != len(identities)
    ):
        raise ValueError("Unqualified native consumable visual policy")
    definitions = metadata.get("native_effects")
    roots = state.get("effect_ids")
    if (
        not isinstance(definitions, dict)
        or not isinstance(roots, (list, tuple))
        or not set(identities) <= set(roots)
    ):
        raise ValueError("Missing native consumable visual root")
    breed, sex = character.get("breed"), character.get("sex")
    if type(breed) is not int or type(sex) not in (int, bool) or sex not in (0, 1):
        raise ValueError("Missing native transformation breed or sex")
    from wakfu_server.combat_conditions import (
        ConditionActor,
        ConditionContext,
        evaluate_condition,
    )
    from wakfu_server.combat_local_criteria import parse_local_criterion

    actor = ConditionActor(breed_id=breed, native_sex=int(sex), is_native_fighter=True)
    context = ConditionContext(actors={"caster": actor, "target": actor})
    selected = []
    for identity in roots:
        if identity not in identities:
            continue
        node = definitions.get(str(identity))
        if (
            not isinstance(node, dict)
            or node.get("id") != identity
            or node.get("generic") != 400
            or node.get("runner") != "eXE"
            or node.get("subscription") is not False
            or node.get("params") != []
            or node.get("values") != []
            or node.get("children") != []
        ):
            raise ValueError("Unqualified native transformation effect")
        native = node.get("native_metadata", {})
        if native.get("target_masks") != [None] * 7:
            raise ValueError(
                "Native transformation must not emit or subscribe to events"
            )
        selector = native.get("native_target_selector", {})
        if selector.get("class") != "fcE" or selector.get("mask") not in (1, 2):
            raise ValueError("Unsupported native transformation target")
        phases = native.get("native_hmi_actions")
        if not isinstance(phases, dict) or not set(phases) <= PHASES:
            raise ValueError("Missing native transformation HMI phases")
        kinds = set()
        for actions in phases.values():
            if not isinstance(actions, list):
                raise ValueError("Invalid native transformation HMI actions")
            for action in actions:
                if (
                    not isinstance(action, dict)
                    or type(action.get("id")) is not int
                    or action["id"] <= 0
                    or action.get("type") not in HMI_TYPES
                    or type(action.get("aYc")) is not bool
                    or type(action.get("aYd")) is not bool
                ):
                    raise ValueError("Unqualified native transformation HMI action")
                kinds.add(action["type"])
        if not kinds & VISUAL_TYPES:
            raise ValueError("Native transformation has no visual operation")
        criterion = node.get("criteria")
        if not isinstance(criterion, str):
            raise ValueError("Invalid native visual criterion")
        if criterion.strip():
            tree = parse_local_criterion(criterion)
            if any(
                isinstance(part, ast.Call)
                and (
                    not isinstance(part.func, ast.Name)
                    or part.func.id not in ("IsBreed", "IsSex")
                )
                for part in ast.walk(tree)
            ):
                raise ValueError("Unqualified native visual criterion context")
            if not evaluate_condition(criterion, context):
                continue
        selected.append(node)
    if not selected:
        raise ValueError("No native transformation applies to this character")
    return tuple(selected)
