"""eXR341 weighted, ordered, without-replacement child lottery.

Eligibility is checked at parent fRR before lottery, without amQ population
filter or subscription shortcut. GS.ne(total) uses [0,total), then cumulative
int(float32(sum)+weight) >= roll (including native zero-boundary behavior).
"""
import math
from dataclasses import replace
from .combat_parameters import _float32
from .combat_effect_groups import EffectGroupMode
from .combat_conditions import evaluate_condition


def _int(value):
    if math.isnan(value):
        return 0
    return max(-(1 << 31), min((1 << 31) - 1, math.trunc(value)))


def random_group_mode(effect, values):
    parameters = values["parameters"]
    if effect["effect_class"] != 341 or len(parameters) not in (1, 2, 3):
        raise ValueError("Unsupported native eXR parameters")
    # eXR.bbA/bbB route from raw eVn.So(1); c() independently evaluates
    # parameter 2 to decide whether the selected child receives target PV.
    raw_parameters = effect.get("parameters")
    if len(parameters) >= 2:
        if not isinstance(raw_parameters, (tuple, list)) or len(raw_parameters) < 2:
            raise ValueError("Missing raw native eXR So(1)")
        raw_target = raw_parameters[1]
        if type(raw_target) not in (int, float):
            raise ValueError("Invalid raw native eXR So(1)")
        on_target = raw_target == 1
    else:
        on_target = True
    return EffectGroupMode(
        on_target=on_target,
        transmit_target=len(parameters) < 3 or parameters[2] == 1,
    )


def weighted_children(candidates, count, *, draw_integer):
    rows = tuple(candidates)
    if (
        type(count) is not int
        or not -(1 << 31) <= count < (1 << 31)
        or not callable(draw_integer)
    ):
        raise ValueError("Missing native eXR count/RNG")
    if len({reference for reference, _ in rows}) != len(rows):
        raise ValueError("Unverified duplicate native eXR child identities")
    weights = []
    total = 0
    for reference, probability in rows:
        if (
            type(reference) is not int
            or type(probability) not in (int, float)
            or not math.isfinite(probability)
        ):
            raise ValueError("Invalid native eXR candidate")
        probability = _float32(probability)
        weights.append((reference, probability))
        total = _int(_float32(_float32(total) + probability))
    selected = []
    for _ in range(max(0, count)):
        if total <= 0:
            raise ValueError(
                "Native GS.ne requires positive remaining probability total"
            )
        roll = draw_integer(total)
        if type(roll) is not int or not 0 <= roll < total:
            raise ValueError("Invalid native eXR bounded integer RNG")
        cumulative = 0
        for reference, probability in weights:
            if reference in selected:
                continue
            cumulative = _int(_float32(_float32(cumulative) + probability))
            if cumulative >= roll:
                selected.append(reference)
                total = _int(_float32(_float32(total) - probability))
                break
    return tuple(selected)


class RandomGroupAuthority:
    def __init__(self, *, effects, condition_context, draw_integer):
        self.effects, self.conditions, self.draw = (
            effects,
            condition_context,
            draw_integer,
        )

    def __call__(self, preview, plan, effect, values, invocation, children):
        random_group_mode(effect, values)
        candidates = []
        for reference in children:
            child = self.effects[str(reference)]
            if not child["minimum_level"] <= invocation.level <= child["maximum_level"]:
                continue
            # eXR.t evaluates amb with source=NULL (not event trigger context).
            criteria_inv = replace(
                invocation, reference=reference, native_trigger_context=None
            )
            if child["criteria"].strip() and not evaluate_condition(
                child["criteria"], self.conditions(preview, plan, child, criteria_inv)
            ):
                continue
            probability = _float32(
                _float32(child["probability_base"])
                + _float32(_float32(child["probability_per_level"]) * invocation.level)
            )
            candidates.append((reference, probability))
        return weighted_children(
            candidates, values["parameters"][0], draw_integer=self.draw
        )


def probability_bypass_context(payload):
    """eVt.a(true,false) updates builder fields, without protobuf duplicates."""
    from wakfu_server.wire import proto_fields
    from .combat_effects import _integer, _varint

    result = [_integer(1, 1), _integer(2, 0)]
    seen = set()
    for tag, value in proto_fields(payload):
        field, wire = tag >> 3, tag & 7
        if field in seen:
            raise ValueError("Duplicate native eVt context field")
        seen.add(field)
        if field in (1, 2):
            if wire != 0:
                raise ValueError("Invalid native eVt boolean wire type")
            continue
        if wire == 0:
            result.append(_varint(tag) + _varint(value))
        elif wire == 2:
            result.append(_varint(tag) + _varint(len(value)) + value)
        else:
            raise ValueError("Unaudited native eVt context wire type")
    return b"".join(result)
