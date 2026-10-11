"""faK/faF/faG/faI/faH native ordering before the signed target cap.

Coordinates are the supplied effect target cell, rather than caster position.
Only definitions exported from the installed native registry are accepted.
Flag8 requires its separately exported identity and actual PA provider.
Flag25 without8 and implicit area sorting remain separate audits.
"""
from wakfu_server import native_catalog as protocol_catalog
from functools import lru_cache
from functools import cmp_to_key
import json
from wakfu_server.paths import DATA_ROOT


@lru_cache(maxsize=1)
def native_target_ordering():
    return protocol_catalog.load(DATA_ROOT / "native-target-ordering.json")


@lru_cache(maxsize=1)
def native_health_target_ordering():
    return protocol_catalog.load(DATA_ROOT / "native-health-target-ordering.json")


def validate_native_target_ordering_identity(effect, reference, *, metadata=None):
    flags = effect.get("native_effect_flags", ())
    health = 8 in flags
    if metadata is None:
        metadata = (
            native_health_target_ordering() if health else native_target_ordering()
        )
    row = metadata.get(str(reference))
    if (
        row is None
        or row["effect_class"] != effect["effect_class"]
        or set(row["native_effect_flags"]) != set(flags)
        or health
        and row.get("ordering_contract") != "faI.PV.a.sgC.PA.aYS.aYU.float32.asc.v1"
    ):
        prefix = "health-percent " if health else ""
        raise ValueError(
            "Missing or conflicting native " + prefix + "target ordering identity"
        )
    maximum = row["maximum_targets"]
    if type(maximum) is not int or not -128 <= maximum <= 127:
        raise ValueError("Native target count must be signed byte")
    return row


def _int32(value):
    return (value + (1 << 31)) % (1 << 32) - (1 << 31)


def native_xy_distance(position, cell):
    # aBn.cG: Java int subtraction, Math.abs(MIN_VALUE)=MIN_VALUE, int sum.
    def absolute(value):
        value = _int32(value)
        return value if value == -(1 << 31) else abs(value)

    return _int32(absolute(cell[0] - position[0]) + absolute(cell[1] - position[1]))


def order_native_targets(
    effect, invocation, targets, *, metadata=None, health_operand=None
):
    targets = tuple(targets)
    flags = effect.get("native_effect_flags", ())
    if not set(flags).intersection((8, 14, 26)):
        return targets
    if 25 in flags and 8 not in flags:
        raise ValueError(
            "Native health-percent ordering takes precedence and is unaudited"
        )
    row = validate_native_target_ordering_identity(
        effect, invocation.reference, metadata=metadata
    )
    maximum = row["maximum_targets"]
    if type(maximum) is not int or not -128 <= maximum <= 127:
        raise ValueError("Native target count must be signed byte")
    if 8 in flags:
        from .combat_target_health_ordering import (
            NativeHealthOperand,
            compare_native_health,
        )

        if not callable(health_operand):
            raise ValueError("Missing actual native health-percent PA provider")
        operands = {}
        for target in targets:
            operand = health_operand(target)
            if not isinstance(operand, NativeHealthOperand):
                raise ValueError("Missing actual native health-percent PA operand")
            operands[id(target)] = operand
        result = tuple(
            sorted(
                targets,
                key=cmp_to_key(
                    lambda left, right: compare_native_health(
                        operands[id(left)], operands[id(right)]
                    )
                ),
            )
        )
        return result[:maximum] if maximum > 0 else result
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
