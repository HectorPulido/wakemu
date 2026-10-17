"""XP thresholds extracted offline from the installed client's own MP curve."""
from wakfu_server.character_levels import (
    XP_BY_LEVEL,
    MAX_CHARACTER_LEVEL,
    validate_character_level,
)


def level_xp(level):
    validate_character_level(level)
    return XP_BY_LEVEL[level]


def character_xp(character):
    """Authoritative earned total, falling back to native level threshold."""
    minimum = level_xp(character["level"])
    total = character.get("xp", minimum)
    if type(total) is not int or not minimum <= total < 2**63:
        raise ValueError("Character XP is outside its native level range")
    if character["level"] < MAX_CHARACTER_LEVEL and total >= level_xp(
        character["level"] + 1
    ):
        raise ValueError("Character XP and persisted level are inconsistent")
    return total
