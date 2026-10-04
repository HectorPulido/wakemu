"""Native eYt912 action-cost and eYv910 spell-cost child level functions.

These use different native sources: paid eWf byte fields vs fyF live costs.
A caller must provide an audited resolved source snapshot; unknown is not zero.
"""
import math
from .combat_parameters import _float32, _integer
from .combat_level_group import _native_float_parameter
from .combat_native_timing_context import native_definition_timing


def weighted_cost_level(weights, costs):
    if len(weights) != 3 or set(costs) != {"ap", "mp", "wp"}:
        raise ValueError("Incomplete native group costs")
    total = _float32(_float32(costs["ap"]) * weights[0])
    total = _float32(total + _float32(_float32(costs["mp"]) * weights[1]))
    total = _float32(total + _float32(_float32(costs["wp"]) * weights[2]))
    # Math.round(float): saturating int, ties toward positive infinity.
    return _integer(math.floor(total + 0.5) if math.isfinite(total) else total)


def cost_group_override(
    effect, level, *, source_present, cost_source, return_native_override=False
):
    family = effect["effect_class"]
    if family not in (910, 912) or len(effect["parameters"]) != 18:
        raise ValueError("Unsupported native triggering-cost group definition")
    if (
        type(level) is not int
        or not -32768 <= level <= 32767
        or type(source_present) is not bool
    ):
        raise ValueError("Unknown native triggering-cost source or level")
    if not source_present:
        if cost_source is not None:
            raise ValueError("Absent source cannot have costs")
        override = 0 if family == 910 else -1
    else:
        if not isinstance(cost_source, dict) or cost_source.get("runner_class") not in (
            "eWf",
            "other",
        ):
            raise ValueError("Missing audited native source runner classification")
        costs = None
        if family == 912:
            if cost_source["runner_class"] != "eWf":
                override = -1
            else:
                costs = cost_source.get("action_costs")
                if (
                    not isinstance(costs, dict)
                    or set(costs) != {"ap", "mp", "wp"}
                    or any(
                        type(v) is not int or not -128 <= v <= 127
                        for v in costs.values()
                    )
                ):
                    raise ValueError("Missing actual signed-byte eWf action costs")
        else:
            spell = cost_source.get("spell_context")
            if not isinstance(spell, dict) or type(spell.get("present")) is not bool:
                raise ValueError("Missing native triggering spell context")
            if not spell["present"]:
                override = 0
            elif type(spell.get("container_type")) is not int:
                raise ValueError("Missing native triggering spell container type")
            elif spell["container_type"] != 11:
                override = 0
            else:
                costs = spell.get("resolved_costs")
                if (
                    not isinstance(costs, dict)
                    or set(costs) != {"ap", "mp", "wp"}
                    or any(
                        type(v) is not int or not -(1 << 31) <= v < (1 << 31)
                        for v in costs.values()
                    )
                ):
                    raise ValueError("Missing authoritative native fyF spell costs")
        if costs is not None:
            weights = tuple(
                _native_float_parameter(effect["parameters"], i, level)
                for i in (6, 7, 8)
            )
            override = weighted_cost_level(weights, costs)
    if return_native_override:
        return override
    return level if override == -1 else ((override + 32768) % 65536) - 32768


def runtime_group_level(
    effect,
    values,
    invocation,
    actors,
    *,
    return_native_override=False,
    cost_resolver=None
):
    native_definition_timing(effect, invocation.level)
    source = invocation.native_trigger_context
    if source is not None and not isinstance(source, dict):
        raise ValueError("Missing audited native triggering context")
    costs = None if source is None else source.get("cost_source")
    if source is not None and callable(cost_resolver):
        costs = cost_resolver(effect, invocation, costs)
    return cost_group_override(
        effect,
        invocation.level,
        source_present=source is not None,
        cost_source=costs,
        return_native_override=return_native_override,
    )
