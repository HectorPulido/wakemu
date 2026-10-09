"""XP thresholds extracted offline from the installed client's own MP curve."""
from wakfu_server import native_catalog as protocol_catalog
from .paths import DATA_ROOT
import json
from pathlib import Path

XP_BY_LEVEL = {
    int(level): xp
    for level, xp in protocol_catalog.load(DATA_ROOT / "level-xp.json")[
        "xp_by_level"
    ].items()
}


def level_xp(level):
    if type(level) is not int or level not in XP_BY_LEVEL:
        raise ValueError("Character level must be between 1 and 200")
    return XP_BY_LEVEL[level]


def character_xp(character):
    """Authoritative earned total, falling back to native level threshold."""
    minimum = level_xp(character["level"])
    total = character.get("xp", minimum)
    if type(total) is not int or not minimum <= total < 2**63:
        raise ValueError("Character XP is outside its native level range")
    if character["level"] < 200 and total >= level_xp(character["level"] + 1):
        raise ValueError("Character XP and persisted level are inconsistent")
    return total
