"""Soft local composition pressure; no species-specific quotas or population caps."""

SPECIAL = {"boss", "ultimate_boss", "raid_boss", "archmonster", "arch"}


def reproduction_factor(size):
    """Young groups establish quickly; established groups mostly seed neighbors."""
    return 2.0 if size < 4 else 1.2 if size == 4 else 0.8


def valid_transition(reference, target, stages, *, allow_regression=False):
    """Authorize monotone maturation; historical receipts opt into old rules."""
    source, destination = stages.get(reference), stages.get(target)
    if source is None or destination is None or source[0] is not destination[0]:
        return False
    family, rank = source
    target_rank = destination[1]
    if target_rank < rank and not allow_regression:
        return False
    candidate = next(
        c
        for c in family["tiers"][target_rank]["candidates"]
        if c["reference"] == target
    )
    source_candidate = next(
        c for c in family["tiers"][rank]["candidates"] if c["reference"] == reference
    )
    if candidate["min_level"] < source_candidate["min_level"] and not allow_regression:
        return False
    from .monster_family_stages import initial_candidates, publication_viable

    if not publication_viable(candidate["reference"], candidate["min_level"]):
        return False
    if target_rank == 0:
        birth_pool = initial_candidates(family["family_id"])
        if birth_pool and target not in {row["reference"] for row in birth_pool}:
            return False
    if candidate.get("boss_classification") in SPECIAL:
        return (
            candidate.get("boss_classification")
            in {"boss", "ultimate_boss", "raid_boss"}
            and target_rank == rank + 1
        )
    active = [
        tier["rank"]
        for tier in family["tiers"]
        if any(
            c.get("boss_classification") not in SPECIAL
            and publication_viable(c["reference"], c["min_level"])
            for c in tier["candidates"]
        )
    ]
    return _neighboring(rank, target_rank, active)


def _neighboring(rank, target, active):
    """Allow an invalid historical source to exit to its closest valid bands."""
    if target not in active:
        return False
    if rank in active:
        return abs(active.index(rank) - active.index(target)) <= 1
    lower = [value for value in active if value < rank]
    upper = [value for value in active if value > rank]
    return target in ([lower[-1]] if lower else []) + ([upper[0]] if upper else [])
