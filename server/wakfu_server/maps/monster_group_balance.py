"""Soft local composition pressure; no species-specific quotas or population caps."""
import math
from collections import Counter

SPECIAL = {"boss", "ultimate_boss", "raid_boss", "archmonster", "arch"}


def reproduction_factor(size):
    """Young groups establish quickly; established groups mostly seed neighbors."""
    return 2.0 if size < 4 else 1.2 if size == 4 else 0.8


def choose_transition(reference, stages, configuration, members, draw, choose):
    """Sample adjacent ordinary stages with reversible, composition-aware odds.

    High stages have declining target mass and stronger crowding pressure.
    Targets are soft: even a crowded stage retains nonzero probability.
    """
    family, rank = stages[reference]
    tiers = family["tiers"]
    size = len(members)
    # Exclude the subject exactly once, including duplicate references.
    counts = Counter(
        stages[m["ref"]][1]
        for m in members
        if m["ref"] in stages and stages[m["ref"]][0] is family
    )
    counts[rank] = max(0, counts[rank] - 1)
    from .monster_family_stages import publication_viable

    ordinary = [
        [
            c
            for c in tier["candidates"]
            if c.get("boss_classification") not in SPECIAL
            and publication_viable(c["reference"], c["min_level"])
        ]
        for tier in tiers
    ]
    # Keep the native farming loop: initial tutorial forms are not alternative
    # maturation targets when the family has validated seed-producing forms.
    from .monster_family_stages import initial_candidates

    birth_pool = initial_candidates(family["family_id"])
    if birth_pool and ordinary:
        initial_refs = {candidate["reference"] for candidate in birth_pool}
        ordinary[0] = [
            candidate
            for candidate in ordinary[0]
            if candidate["reference"] in initial_refs
        ]
    current = next(c for c in tiers[rank]["candidates"] if c["reference"] == reference)
    if current.get("boss_classification") in SPECIAL:
        return None
    up_bosses = (
        [
            c
            for c in tiers[rank + 1]["candidates"]
            if c.get("boss_classification") in {"boss", "ultimate_boss", "raid_boss"}
            and publication_viable(c["reference"], c["min_level"])
        ]
        if rank + 1 < len(tiers)
        else []
    )
    boss_mass = configuration["boss_probability"] if up_bosses else 0.0
    if draw < boss_mass:
        return choose(up_bosses)
    speed = 1.8 if size < 4 else 1.0 if size == 4 else 0.45
    probability = min(1.0 - boss_mass, configuration["base_probability"] * speed)
    if draw >= boss_mass + probability or probability <= 0:
        return None
    active = [i for i, candidates in enumerate(ordinary) if candidates]
    if not active:
        return None
    # Group size lifts the tail gradually; small groups strongly favor basics.
    decay = min(0.48, 0.20 + size * 0.035)
    raw = {
        i: (decay * max(0.001, configuration["stage_decay"])) ** active.index(i)
        for i in active
    }
    total = sum(raw.values())
    options = []
    for target in active:
        if not _neighboring(rank, target, active):
            continue
        candidates = ordinary[target]
        if not candidates:
            continue
        expected = size * raw[target] / total
        crowding = math.exp(-min(50.0, counts[target] / max(0.20, expected)))
        weight = raw[target] * crowding
        options.append((candidates, weight))
    if not options:
        return None
    point = (draw - boss_mass) / probability * sum(weight for _, weight in options)
    for candidates, weight in options:
        if point < weight:
            selected = choose(candidates)
            return None if selected["reference"] == reference else selected
        point -= weight
    selected = choose(options[-1][0])
    return None if selected["reference"] == reference else selected


def valid_transition(reference, target, stages):
    """Receipt/prepared authorization mirrors ordinary adjacency and rare bosses."""
    source, destination = stages.get(reference), stages.get(target)
    if source is None or destination is None or source[0] is not destination[0]:
        return False
    family, rank = source
    target_rank = destination[1]
    candidate = next(
        c
        for c in family["tiers"][target_rank]["candidates"]
        if c["reference"] == target
    )
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
