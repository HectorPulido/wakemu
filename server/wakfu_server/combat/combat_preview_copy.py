"""Private PA-map copies for the same ordinary deepcopy transaction memo.

The mutable dictionaries are always duplicated. Only exact immutable scalar
keys/values are reused, as ordinary deepcopy already does. Other structures
and dictionary subclasses retain their existing deepcopy/observer contracts.
"""
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
    if type(fight) is not Fight or type(fight.actors) is not dict:
        return memo
    for actor in fight.actors.values():
        if type(actor) is not Actor:
            continue
        for name in _PA_FIELDS:
            value = getattr(actor, name, None)
            if type(value) is not dict or id(value) in memo:
                continue
            if all(_scalar(key) and _scalar(item) for key, item in value.items()):
                memo[id(value)] = value.copy()
                # Match deepcopy's source keep-alive rule for preseeded IDs.
                # This temporary memo is never attached to the private graph.
                memo.setdefault(id(memo), []).append(value)
    return memo
