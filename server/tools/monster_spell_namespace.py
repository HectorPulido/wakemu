"""Validate spell records before importing them into the NPC spell namespace."""


def validate_spell_namespace(spells):
    """Reject state-shaped definitions even when their numeric IDs match spells."""
    for reference, row in spells.items():
        levels = row.get("levels")
        if not isinstance(levels, list) or not levels:
            raise ValueError(f"Invalid native spell levels: {reference}")
        for level in levels:
            if (
                not isinstance(level, list)
                or len(level) != 3
                or type(level[0]) is not int
                or type(level[1]) is not int
                or not isinstance(level[2], list)
                or any(type(effect) is not int for effect in level[2])
            ):
                raise ValueError(
                    f"Non-spell definition in spell namespace: {reference}"
                )
