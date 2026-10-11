"""Classify native resource domains from their actual profession actions."""


def _has_profession(reference, profession):
    """Classify non-monsters by their native profession actions."""
    from .planting import RESOURCES

    if type(reference) is not int:
        return False
    definition = RESOURCES.get(reference)
    return bool(
        definition is not None
        and not definition["monster_resource"]
        and any(
            action.get("profession_id") == profession
            for stage in definition.get("stage_definitions", ())
            for action in stage.get("actions", ())
        )
    )


def is_mineral(reference):
    """Identify native mining resources."""
    return _has_profession(reference, 73)


def is_fish(reference):
    """Identify native fishing resources."""
    return _has_profession(reference, 75)


def is_fixed_resource(reference):
    return is_mineral(reference) or is_fish(reference)
