"""Original fef/fel/fei disengagement arithmetic over owned fighter facts."""
import math
import struct
from types import SimpleNamespace


def _f(value):
    return struct.unpack(">f", struct.pack(">f", value))[0]


def _i(value):
    return (value + (1 << 31)) % (1 << 32) - (1 << 31)


def native_tackle_loss(tackles, dodge, level, facing):
    """fef: descending weighted lock, float32 arithmetic, floor/ceil split."""
    if (
        not isinstance(tackles, (tuple, list))
        or any(type(n) is not int or not -(1 << 31) <= n < (1 << 31) for n in tackles)
        or type(dodge) is not int
        or not -(1 << 31) <= dodge < (1 << 31)
        or type(level) is not int
        or not -(1 << 15) <= level < (1 << 15)
        or facing not in ("FRONT", "SIDE", "BACK")
    ):
        raise ValueError("Missing original disengagement arithmetic inputs")
    if not tackles:
        return 0, 0
    total = 0
    for rank, tackle in enumerate(sorted(tackles, reverse=True), 1):
        # Java integer division truncates toward zero, including negative PC7.
        weighted = (abs(tackle) // rank) * (-1 if tackle < 0 else 1)
        total = _i(total + weighted)
    lock, dodge = max(0, total), max(0, dodge)
    ratio = _f(_f(2.3333333) * _f(_i(lock - dodge)))
    if lock != dodge:
        denominator = _f(_i(lock + dodge))
        ratio = (
            _f(ratio / denominator) if denominator else math.copysign(math.inf, ratio)
        )
    ratio = min(1.0, max(-1.0, ratio))
    scale = min(_f(_f(0.5) + _f(_f(level) / _f(200))), 1.0)
    amount = _f(_f(_f(_f(ratio + 1.0) * 8.0) / 2.0) * scale)
    amount = _f(amount + {"FRONT": 0, "SIDE": -1, "BACK": -2}[facing])
    total = math.floor(max(0.0, amount))
    mp = math.ceil(_f(_f(total) / 2.0))
    return total - mp, mp


def _contact(a, b, radius_a, radius_b):
    """fel: square radius contact without outer diagonal or same XYZ."""
    if a == b:
        return False
    radius = radius_a + radius_b + 1
    dx, dy = abs(_i(a[0] - b[0])), abs(_i(a[1] - b[1]))
    return dx <= radius and dy <= radius and (dx != radius or dy != radius)


def movement_tackle_cost(fight, actor, path):
    """fei evaluates departures, preserving positive-radius one-time use."""
    # Legacy pure FSM fixtures have no native characteristic domain. Real owned
    # snapshots must never silently lose their disengagement authority.
    if actor.effect_stats is None and not hasattr(
        fight, "native_global_pv_collections"
    ):
        return 0, 0
    provider = getattr(fight, "native_rail_movement_authority", None)
    if not callable(provider) or not callable(getattr(provider, "properties", None)):
        raise ValueError("Missing actual native movement fighter authority")
    from .combat_runtime_adapter import NativeActorAuthority
    from .combat_native_actor_lookup import native_actor_population
    from .combat_ordinary_authority import native_facing

    def facts(candidate):
        metadata = provider(fight, candidate)
        properties = provider.properties(fight, candidate)
        if (
            not isinstance(metadata, NativeActorAuthority)
            or type(metadata.is_carried) is not bool
            or not isinstance(properties, frozenset)
            or any(
                type(metadata.targeting.get(k)) is not bool
                for k in ("baF", "baG", "baK")
            )
        ):
            raise ValueError("Missing original movement status/property authority")
        master = metadata.targeting.get("dpu_id")
        if master is None and "dpu_id" in metadata.targeting:
            master = candidate.id  # Original frG: null dpu falls back to SELF.
        owner = fight.actors.get(master)
        if owner is None or type(owner.team) is not int:
            raise ValueError("Missing actual native movement affiliation")
        return metadata, properties, owner.team

    own, properties, team = facts(actor)
    if (
        own.is_carried
        or own.targeting["baG"]
        or own.targeting["baK"]
        or 69 in properties
    ):
        return 0, 0
    if (
        not isinstance(actor.effect_stats, dict)
        or type(actor.effect_stats.get(8)) is not int
    ):
        raise ValueError("Missing actual native movement dodge characteristic")
    if type(actor.effective_level) is not int or type(actor.physical_radius) is not int:
        raise ValueError("Missing actual native movement level/radius")
    candidates = []
    for candidate in native_actor_population(fight):
        if hasattr(fight, "native_global_pv_collections"):
            from .combat_global_pv_collections import global_fighter_guards

            # Original fdt.a applies fdU (in-play) before relationship/PB
            # predicates. Retained corpses need no live movement authority.
            if not global_fighter_guards(fight, candidate.id)["baF"]:
                continue
        metadata, pb, affiliation = facts(candidate)
        if (
            not metadata.targeting["baF"]
            or affiliation == team
            or metadata.is_carried
            or 15 in pb
        ):
            continue
        stats = candidate.effect_stats
        if not isinstance(stats, dict):
            raise ValueError("Missing actual tackler characteristic map")
        # Original fef explicitly excludes absent PC7 and invisible fighters.
        if 7 not in stats or 5 in pb or 17 in pb:
            continue
        if type(stats[7]) is not int or type(candidate.physical_radius) is not int:
            raise ValueError("Missing actual native tackler radius/value")
        candidates.append(candidate)
    ap = mp = 0
    for position in [actor.position, *path[:-1]]:
        touching = [
            c
            for c in candidates
            if _contact(c.position, position, c.physical_radius, actor.physical_radius)
        ]
        facings = [
            native_facing(SimpleNamespace(position=position), c) for c in touching
        ]
        facing = (
            "FRONT" if "FRONT" in facings else "SIDE" if "SIDE" in facings else "BACK"
        )
        loss_ap, loss_mp = native_tackle_loss(
            [c.effect_stats[7] for c in touching],
            actor.effect_stats[8],
            actor.effective_level,
            facing,
        )
        ap, mp = _i(ap + loss_ap), _i(mp + loss_mp)
        used = {c.id for c in touching if c.physical_radius > 0}
        candidates = [c for c in candidates if c.id not in used]
    return ap, mp
