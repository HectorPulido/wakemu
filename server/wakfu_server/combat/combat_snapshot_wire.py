"""tA/tB characteristics from installed native snapshots, without gear replay.

Native tB order: PC byte, raw current, raw minimum, raw maximum, maximum
percentage modifier. Server snapshots use effective maxima; fresh initialization
preserves percentage/raw-maximum metadata for the owned HP percentage source.
"""
import struct
from .combat_actor_snapshot import native_actor_catalog, _int32


def snapshot_characteristics(actor):
    from .combat_hud_resource import sync_actor_hud_resource

    sync_actor_hud_resource(actor)
    mappings = [
        actor.effect_stats,
        actor.effect_minima,
        actor.effect_maxima,
        getattr(actor, "effect_percentages", None),
        getattr(actor, "effect_base_maxima", None),
    ]
    if any(not isinstance(v, dict) for v in mappings):
        raise ValueError("Missing native wire characteristic metadata")
    stats, minima, maxima, percentages, bases = mappings
    if not stats or any(set(v) != set(stats) for v in mappings) or len(stats) > 65535:
        raise ValueError("Incomplete native wire characteristic metadata")
    for identity, live in (
        (1, actor.hp),
        (2, actor.ap),
        (3, actor.mp),
        (35, actor.initiative),
    ):
        if stats.get(identity) != live:
            raise ValueError("Characteristic snapshot disagrees with live actor")
    for identity, live in ((1, actor.max_hp), (2, actor.max_ap), (3, actor.max_mp)):
        if maxima.get(identity) != live:
            raise ValueError("Characteristic maximum disagrees with live actor")
    definitions = native_actor_catalog()["characteristics"]
    out = []
    for identity, current in sorted(stats.items()):
        pct = percentages[identity]
        # Preserve raw PA maxima/minima even when percentage is zero; eWO can
        # move raw bounds below hard minimum while effective bounds stay zero.
        maximum = bases[identity]
        raw_minima = getattr(actor, "effect_base_minima", None)
        if not isinstance(raw_minima, dict) or identity not in raw_minima:
            raise ValueError("Missing native raw minimum snapshot")
        minimum = raw_minima[identity]
        if (
            type(identity) is not int
            or str(identity) not in definitions
            or any(
                type(v) is not int or not -(1 << 31) <= v < (1 << 31)
                for v in (current, minimum, maximum, pct)
            )
        ):
            raise ValueError("Invalid native wire characteristic")
        product = _int32(maximum * pct)
        adjustment = abs(product) // 100 * (1 if product >= 0 else -1)
        row = definitions[str(identity)]
        effective = min(
            row["hard_maximum"], max(row["hard_minimum"], _int32(maximum + adjustment))
        )
        effective_minimum = max(row["hard_minimum"], min(row["hard_maximum"], minimum))
        if (
            effective != maxima[identity]
            or minima[identity] != effective_minimum
            or not effective_minimum <= current
            or (identity != 1 and current > maxima[identity])
        ):
            raise ValueError("Unknown native percentage/bound mutation")
        out.append(struct.pack(">Biiii", identity, current, minimum, maximum, pct))
    return struct.pack(">H", len(out)) + b"".join(out)
