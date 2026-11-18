"""Recognize immediate ordered NPC area groups already handled by dispatcher."""


def immediate_state_group(effect, effects):
    """Return the attested no-limit actor group child, or reject other groups.

    This only certifies the parent recipient query. The transaction still runs
    normal group ordering, state ownership, child selectors and conditions.
    """
    from .combat_effect_targets import native_selector_policy

    children = effect.get("children")
    parameters = effect.get("parameters")
    if (
        effect.get("effect_class") != 330
        or effect.get("parameter_count") != 1
        or not isinstance(parameters, (list, tuple))
        or tuple(parameters) != (0.0, 0.0)
        or not isinstance(children, (list, tuple))
        or len(children) != 1
    ):
        return None
    child = effects.get(str(children[0]))
    if (
        not isinstance(child, dict)
        or child.get("effect_class") != 321
        or child.get("children")
        or child.get("criteria", "").strip()
        or child.get("native_target_selector") != {"class": "fcE", "mask": 2}
        or child.get("area_class") != "anA"
        or child.get("area_native") != "empty"
        or child.get("application_flag") != "NONE"
        or child.get("removal_flag") != "NONE"
    ):
        return None
    native_selector_policy(child)
    return child


def immediate_target_state_group(effect, effects):
    """Recognize an ordered native local apply/remove sequence on each target.

    Unlike the legacy caster-removal group, these children retain the parent's
    selected actor through their original point/in-area selectors. No target,
    state, order, probability or condition is changed by this qualification.
    """
    from .combat_effect_targets import native_selector_policy

    children = effect.get("children")
    if (
        effect.get("effect_class") != 330
        or effect.get("parameter_count") != 1
        or tuple(effect.get("parameters", ())) != (0.0, 0.0)
        or not isinstance(children, (list, tuple))
        or not 1 <= len(children) <= 32
        or len(set(children)) != len(children)
        or effect.get("criteria", "") != ""
    ):
        return None
    result = []
    for identity in children:
        child = effects.get(str(identity))
        if (
            not isinstance(child, dict)
            or child.get("effect_class") not in (304, 321)
            or child.get("children")
            or child.get("criteria", "").strip()
            or child.get("native_target_selector") != {"class": "fcE", "mask": 1}
            or child.get("area_class") != "anD"
            or child.get("area_native") != "point"
            or child.get("target_masks") != [None] * 7
            or child.get("application_flag") != "NONE"
            or child.get("removal_flag") != "NONE"
        ):
            return None
        native_selector_policy(child)
        result.append(child)
    return tuple(result)
