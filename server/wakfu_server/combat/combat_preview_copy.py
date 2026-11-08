"""Private PA-map copies for the same ordinary deepcopy transaction memo.

The mutable dictionaries are always duplicated. Only exact immutable scalar
keys/values are reused, as ordinary deepcopy already does. Other structures
and dictionary subclasses retain their existing deepcopy/observer contracts.
"""
from itertools import repeat
from operator import is_

from .combat_retained_collections import OwnedMap
from .combat_state import Actor, Fight

_PA_FIELDS = (
    "effect_stats",
    "effect_minima",
    "effect_maxima",
    "effect_percentages",
    "effect_base_minima",
    "effect_base_maxima",
)


def _scalar(value):
    kind = type(value)
    return kind is int or kind is float or kind is bool or kind is str or value is None


def scalar_actor_memo(fight):
    """Prime one memo without sharing mutable maps or changing actor identity."""
    memo = {}
    if type(fight) is not Fight or (
        type(fight.actors) is not dict and type(fight.actors) is not OwnedMap
    ):
        return memo
    for actor in fight.actors.values():
        if type(actor) is not Actor:
            continue
        for name in _PA_FIELDS:
            value = getattr(actor, name, None)
            if type(value) is not dict or id(value) in memo:
                continue
            # Native PA maps usually contain exact integers. Identity checks
            # do not invoke custom metaclass equality or hashing. The broader
            # scalar contract remains unchanged for every other exact dict.
            integers = all(map(is_, map(type, value.keys()), repeat(int))) and all(
                map(is_, map(type, value.values()), repeat(int))
            )
            if integers or all(
                _scalar(key) and _scalar(item) for key, item in value.items()
            ):
                memo[id(value)] = value.copy()
                # Match deepcopy's source keep-alive rule for preseeded IDs.
                # This temporary memo is never attached to the private graph.
                memo.setdefault(id(memo), []).append(value)
    return memo


def runtime_scalar_actor_memo(runtime):
    """Prime fresh native runtime copies; custom runtimes keep ordinary deepcopy."""
    from .combat_runtime_messages import RuntimeMessages

    if (
        type(runtime) is not RuntimeMessages
        or RuntimeMessages.__getattribute__ is not object.__getattribute__
    ):
        return {}
    return scalar_actor_memo(vars(runtime).get("fight"))
