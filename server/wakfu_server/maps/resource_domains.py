"""Classify native resource domains from their actual profession actions."""


def is_mineral(reference):
    """Mining resources are non-monsters with a native profession73 action."""
    from .planting import RESOURCES

    if type(reference) is not int:
        return False
    definition = RESOURCES.get(reference)
    return bool(
        definition is not None
        and not definition["monster_resource"]
        and any(
            action.get("profession_id") == 73
            for stage in definition.get("stage_definitions", ())
            for action in stage.get("actions", ())
        )
    )
