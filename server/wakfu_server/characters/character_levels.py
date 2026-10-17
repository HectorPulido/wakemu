"""Character levels supported by the process-pinned native XP catalog."""
from wakfu_server import native_catalog
from wakfu_server.paths import DATA_ROOT


def supported_xp_curve(document):
    rows = document["xp_by_level"]
    if not isinstance(rows, dict) or not rows:
        raise ValueError("Missing native character XP curve")
    values = {}
    for key, xp in rows.items():
        if not isinstance(key, str) or not key.isdecimal() or str(int(key)) != key:
            raise ValueError("Invalid native character level key")
        level = int(key)
        if not 1 <= level <= 32767 or type(xp) is not int or not 0 <= xp < 2**63:
            raise ValueError("Invalid native character XP threshold")
        values[level] = xp
    if sorted(values) != list(range(1, max(values) + 1)):
        raise ValueError("Native character XP curve is not contiguous")
    if values[1] != 0 or any(
        values[level] <= values[level - 1] for level in range(2, max(values) + 1)
    ):
        raise ValueError("Native character XP curve is not strictly increasing")
    return values


XP_BY_LEVEL = supported_xp_curve(native_catalog.load(DATA_ROOT / "level-xp.json"))
MIN_CHARACTER_LEVEL = 1
MAX_CHARACTER_LEVEL = max(XP_BY_LEVEL)


def validate_character_level(level):
    if (
        type(level) is not int
        or not MIN_CHARACTER_LEVEL <= level <= MAX_CHARACTER_LEVEL
    ):
        raise ValueError(
            f"Character level must be between {MIN_CHARACTER_LEVEL} and {MAX_CHARACTER_LEVEL}"
        )
    return level
