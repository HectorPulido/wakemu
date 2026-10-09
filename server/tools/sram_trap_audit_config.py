"""Cheap preflight for the offline trap harness before loading Ready catalogs."""
CANDIDATE_LIMIT = 256
MAXIMUM_ELIGIBLE = 16


def validate_configuration(
    *,
    level,
    spell,
    mover="owner",
    limit=CANDIDATE_LIMIT,
    maximum_eligible=MAXIMUM_ELIGIBLE
):
    if type(level) is not int or not 1 <= level <= 200:
        raise ValueError("Trap audit level must be 1..200")
    if type(spell) is not int or spell not in (5182, 5183):
        raise ValueError("Trap audit requires an original representative grant")
    if mover not in ("owner", "enemy"):
        raise ValueError("Trap audit requires an actual owner or enemy mover")
    if type(limit) is not int or not 1 <= limit <= 4096:
        raise ValueError("Invalid bounded casting candidate limit")
    if type(maximum_eligible) is not int or not 1 <= maximum_eligible <= 16:
        raise ValueError("Invalid eligible casting target count")
