"""faK/faF/faG/faH native stable distance ordering before target cap.

Coordinates are the supplied effect target cell, rather than caster position.
Only definitions exported from the installed native registry are accepted.
Health-percent priority flags8/25 and implicit area sort remain separate audits.
"""
from functools import lru_cache
import json
from .paths import DATA_ROOT


@lru_cache(maxsize=1)
def native_target_ordering():
    return json.loads((DATA_ROOT / "native-target-ordering.json").read_text())


def _int32(value):
    return (value + (1 << 31)) % (1 << 32) - (1 << 31)


def native_xy_distance(position, cell):
    # aBn.cG: Java int subtraction, Math.abs(MIN_VALUE)=MIN_VALUE, int sum.
    def absolute(value):
        value = _int32(value)
        return value if value == -(1 << 31) else abs(value)

    return _int32(absolute(cell[0] - position[0]) + absolute(cell[1] - position[1]))


def order_native_targets(effect, invocation, targets, *, metadata=None):
    targets = tuple(targets)
    flags = effect.get("native_effect_flags", ())
    if not set(flags).intersection((14, 26)):
        return targets
    if set(flags).intersection((8, 25)):
        raise ValueError(
            "Native health-percent ordering takes precedence and is unaudited"
        )
    metadata = native_target_ordering() if metadata is None else metadata
    row = metadata.get(str(invocation.reference))
    if (
        row is None
        or row["effect_class"] != effect["effect_class"]
        or set(row["native_effect_flags"]) != set(flags)
    ):
        raise ValueError("Missing or conflicting native target ordering identity")
    maximum = row["maximum_targets"]
    if type(maximum) is not int or not -128 <= maximum <= 127:
        raise ValueError("Native target count must be signed byte")
    for target in targets:
        if any(
            type(v) is not int or not -(1 << 31) <= v < (1 << 31)
            for v in (*target.position[:2], *invocation.cell[:2])
        ):
            raise ValueError(
                "Native target ordering requires authoritative int32 coordinates"
            )
    # faK checks14 before26. Python sorted, like Java List.sort, preserves ties.
    result = tuple(
        sorted(
            targets,
            key=lambda target: native_xy_distance(target.position, invocation.cell),
            reverse=14 not in flags,
        )
    )
    return result[:maximum] if maximum > 0 else result
