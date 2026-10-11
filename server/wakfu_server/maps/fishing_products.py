"""Fixed primary products for supported native fishing actions."""


def _stack_rules():
    from wakfu_server.inventory_move import STACKS

    return STACKS


def supports_action(rule):
    """Accept only unconditional terminal fishing with a known fixed item."""
    if not isinstance(rule, dict):
        return False
    getters = rule.get("raw_getters")
    item = rule.get("item_reference")
    return bool(
        rule.get("profession_id") == 75
        and rule.get("criteria") == ""
        and isinstance(getters, dict)
        and type(getters.get("cvF")) is int
        and getters["cvF"] in (0, 1)
        and type(item) is int
        and item > 0
        and item in _stack_rules()
    )


def supports_stage(resource_reference, stage):
    """Whether a native fish spot stage is active or an empty stage-1 row."""
    from .planting import RESOURCES
    from .resource_domains import is_fish

    if type(stage) is not int or not is_fish(resource_reference):
        return False
    definition = RESOURCES[resource_reference]
    if stage not in definition.get("stages", ()):
        return False
    step = next(
        (
            row
            for row in definition.get("stage_definitions", ())
            if row.get("stage_id") == stage
        ),
        None,
    )
    if step is None:
        return False
    actions = [
        action
        for action in step.get("actions", ())
        if action.get("profession_id") == 75
    ]
    if stage == 1:
        return not actions
    if not actions or not all(supports_action(action) for action in actions):
        return False
    if any(action["raw_getters"]["cvF"] == 1 for action in actions):
        empty = next(
            (
                row
                for row in definition.get("stage_definitions", ())
                if row.get("stage_id") == 1
            ),
            None,
        )
        if empty is None or any(
            action.get("profession_id") == 75 for action in empty.get("actions", ())
        ):
            return False
    return True


def resolve(_db, rule):
    """Resolve the native primary item; candidate lists are never randomized."""
    if not supports_action(rule):
        raise ValueError("Unsupported native fishing action or primary product")
    return rule["item_reference"]
