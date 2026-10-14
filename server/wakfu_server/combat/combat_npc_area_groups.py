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
