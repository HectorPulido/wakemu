"""Qe.a amount mutation: native owner-specific float32 and rounding rules.

This arithmetic is independent of actor stats. Wiring requires the live
source runner; state levels and damage auxiliary fields use other contracts.
"""
from wakfu_server import native_catalog as protocol_catalog
import math
import json
from pathlib import Path
from .combat_parameters import _float32

_OWNERS = protocol_catalog.load(
    Path(__file__).resolve().parents[2]
    / "protocol"
    / "native-trigger-value-owners.json"
)["effects"]


def mutate_triggering_runner(mode, value, replace):
    """eZL.c mutates the scoped source Qe, never the listener's actor stats."""
    from .combat_final_modifier import triggering_runner_source

    source = triggering_runner_source()
    if source is None or mode < 0:
        return False
    row = _OWNERS.get(str(source.effect_action_id))
    if row is None:
        raise ValueError("Missing original triggering runner mutation owner")
    if row["owner"] == "Qe":
        return False
    runner = source.runner_modifier
    if (
        not isinstance(runner, NativeRunnerAmount)
        or runner.uid != source.uid
        or runner.family != source.effect_action_id
        or runner.owner != row["owner"]
    ):
        raise ValueError("Missing exact live triggering runner amount")
    runner.mutate(mode, value, replace)
    return True


class NativeRunnerAmount:
    """One live Qe amount; PR suppression is sticky, independent of application."""

    def __init__(self, uid, family, *, rng, value=0):
        row = _OWNERS.get(str(family))
        if (
            type(uid) is not int
            or not 0 < uid < 2**63
            or type(family) is not int
            or row is None
            or not callable(rng)
        ):
            raise ValueError("Missing original source runner identity or RNG")
        self.uid, self.family, self.owner, self.rng = uid, family, row["owner"], rng
        self.notification_suppressed = False
        self.additional_mastery = self.additional_resistance = 0
        self.set_calculated(value)

    def set_calculated(self, value):
        if type(value) is not int or not -(2**31) <= value < 2**31:
            raise ValueError("Native source runner amount requires signed int")
        self.value = value

    set_applied = set_calculated

    def mutate(self, mode, value, replace):
        if self.owner == "eXt" and mode in (5, 6):
            if (
                type(value) is not int
                or not -(2**31) <= value < 2**31
                or type(replace) is not bool
            ):
                raise ValueError("Invalid native damage auxiliary modification")
            # eXt ignores replace here: both modes assign UP.bt(float(value)).
            field = "additional_mastery" if mode == 5 else "additional_resistance"
            setattr(self, field, _round(_float32(value), self.rng))
            self.value = max(0, self.value)
            return
        self.value = modify_runner_amount(
            self.owner, self.value, mode, value, replace, rng=self.rng
        )
        if self.owner in ("eWW", "eWN", "eWO") and self.value == 0:
            self.notification_suppressed = True

    def finish_application(self):
        # eZR.a resets rIW after PR notification, before post-apply L3/L4.
        self.notification_suppressed = False


def _int(value):
    # Java f2i/d2i saturate, then truncate; NaN becomes zero.
    if math.isnan(value):
        return 0
    return min(2**31 - 1, max(-(2**31), math.trunc(value)))


def _wrap(value):
    return (value + 2**31) % 2**32 - 2**31


def _round(value, rng):
    floor = math.floor(value)
    fraction = value - floor
    if fraction:
        sample = rng()
        if type(sample) not in (float, int) or not 0 <= sample < 1:
            raise ValueError("Missing native triggering-value rounding sample")
        floor += int(sample < fraction)
    return _int(floor)


def modify_runner_amount(owner, current, mode, value, replace, *, rng):
    if (
        type(current) is not int
        or not -(2**31) <= current < 2**31
        or type(mode) is not int
        or type(value) is not int
        or not -(2**31) <= value < 2**31
        or type(replace) is not bool
    ):
        raise ValueError("Invalid native triggering-value modification")
    if owner == "Qe":
        return current
    if owner not in ("eXt", "eXs", "eWW", "eWN", "eWO"):
        raise ValueError("Native source owner requires a different mutation contract")
    if owner == "eXt" and mode in (5, 6):
        raise ValueError("Native damage auxiliary fields require live runner authority")
    amount = _float32(value)
    if mode == 0:
        ratio = _float32(_float32(_float32(current) * amount) / 100)
        if owner == "eXs":
            current = (
                _int(math.floor(ratio))
                if replace
                else _int(_float32(_float32(current) + ratio))
            )
        elif not replace:
            current = _wrap(current + _round(ratio, rng))
        elif owner == "eXt":
            current = _round(ratio, rng)
    elif mode == 1:
        if replace:
            current = (
                _int(math.floor(amount)) if owner == "eXs" else _round(amount, rng)
            )
        else:
            current = _int(_float32(_float32(current) + amount))
    return max(0, current) if owner == "eXt" else current
