"""Pure native faI comparator; no target registry or actor authority fallback.

Callers must obtain PV.a(sgC), PA.aYS and PA.aYU from an authenticated actual
characteristic container. This module does not infer presence from scalar HP.
"""
from dataclasses import dataclass
import math
import struct


@dataclass(frozen=True)
class NativeHealthOperand:
    present: bool
    current: int | None = None
    maximum: int | None = None

    def __post_init__(self):
        if type(self.present) is not bool:
            raise ValueError("Missing actual PV HP presence operand")
        if self.present:
            for value in (self.current, self.maximum):
                if type(value) is not int or not -(1 << 31) <= value < (1 << 31):
                    raise ValueError("Missing actual PA HP current/maximum operand")
        elif self.current is not None or self.maximum is not None:
            raise ValueError("Absent PA cannot supply HP values")


def _float32(value):
    return struct.unpack(">f", struct.pack(">f", value))[0]


def native_health_percentage(operand):
    if not isinstance(operand, NativeHealthOperand) or not operand.present:
        raise ValueError("Native percentage requires actual present HP PA")
    current, maximum = _float32(operand.current), _float32(operand.maximum)
    if maximum == 0:
        ratio = math.nan if current == 0 else math.copysign(math.inf, current)
    else:
        ratio = _float32(current / maximum)
    return _float32(ratio * 100.0)


def _java_float_compare(left, right):
    if left < right:
        return -1
    if left > right:
        return 1

    # Float.floatToIntBits canonicalizes NaN and compares signed integer bits.
    def bits(value):
        if math.isnan(value):
            return 0x7FC00000
        return struct.unpack(">i", struct.pack(">f", value))[0]

    a, b = bits(left), bits(right)
    return (a > b) - (a < b)


def compare_native_health(left, right):
    """faI.c, including its asymmetric both-absent return1 contract."""
    if not isinstance(left, NativeHealthOperand) or not isinstance(
        right, NativeHealthOperand
    ):
        raise ValueError("Missing native health operand authority")
    if not left.present:
        return 1
    if not right.present:
        return -1
    return _java_float_compare(
        native_health_percentage(left), native_health_percentage(right)
    )


def health_operand_for_pv(fight, target):
    """Read actual scoped PV/PA authority; unknown actors/areas fail closed."""
    from .combat_native_actor_lookup import native_actor
    from .combat_group_pv import group_pa, resolve_group_level_pv

    actor = native_actor(fight, target.id)
    if actor is not None:
        if actor is not target:
            raise ValueError("Native health ordering actor identity mismatch")
        from .combat_hp_raw import hp_raw_present, hp_raw_current

        if not hp_raw_present(actor):
            raise ValueError("Missing native health PA constructor/copy authority")
        pair = group_pa(fight, actor.id, 1)
        minima = getattr(actor, "effect_minima", None)
        if not isinstance(minima, dict) or type(minima.get(1)) is not int:
            raise ValueError("Missing native health PA minimum authority")
        # A validated actual HP.on/copied-PA operand proves this container has
        # sgC. faI uses effective aYS, not the underlying unclamped raw operand.
        hp_raw_current(actor)
        if pair is None or actor.hp != pair[0]:
            raise ValueError("Native health PA effective current mismatch")
        return NativeHealthOperand(True, *pair)
    resolved = resolve_group_level_pv(fight, target.id)
    from .combat_effect_area_targets import NativeAreaTarget

    if (
        not isinstance(target, NativeAreaTarget)
        or getattr(resolved, "native_is_area", False) is not True
        or target.id != resolved.id
        or tuple(target.position) != tuple(resolved.position)
    ):
        raise ValueError("Missing actual native health area PV authority")
    pair = group_pa(fight, target.id, 1)
    return (
        NativeHealthOperand(False) if pair is None else NativeHealthOperand(True, *pair)
    )
