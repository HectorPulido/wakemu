"""Tooling-only native linear empty anchor candidates; never eligibility."""


def ordinary_linear_empty_targets(fight, source, minimum, maximum, casting, fallback):
    if casting.get("linear") is not True:
        return fallback[:2]
    from monster_pending_scenarios import bounded_empty_targets

    candidates = bounded_empty_targets(
        fight,
        source,
        minimum,
        maximum,
        limit=12,
        prefer_linear=True,
        prefer_diagonal=casting.get("diagonal") is True,
    )
    return [
        cell for cell in candidates if cell[0] == source[0] or cell[1] == source[1]
    ][:2]
