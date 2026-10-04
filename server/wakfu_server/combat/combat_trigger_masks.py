"""Native Qi/eZX mask routing, separate from visual OY/HMI actions.

Catalog target_masks actually contains PK.aZG/aZH/aZI/aZJ/aZK/aZL/aZO.
Qi.a/b and eZX.a(byte,Qe,BitSet) intersect one mask, then enqueue apply
(s/Qe.k) or remove (t/Qe.bbO). OY IDs are incremental visual-action IDs;
eVl are effect flags and eVi is the class registry, not combat event IDs.
This module does not invent fightstart/turn/damage/death event bit IDs.
"""
from dataclasses import dataclass
from typing import Iterable, Literal


class UnknownTriggerRouting(ValueError):
    pass


# Indices follow ExportSpellEffectTrees target_masks ordering.
_CHANNELS = {
    1: (0, "apply"),
    2: (1, "apply"),
    3: (3, "apply"),
    4: (2, "remove"),
    5: (4, "apply"),
    6: (5, "apply"),
    10: (0, "apply"),
    20: (1, "apply"),
    30: (3, "apply"),
    40: (2, "remove"),
    60: (5, "apply"),
    11: (0, "apply"),
    21: (1, "apply"),
    31: (3, "apply"),
    41: (2, "remove"),
    61: (5, "apply"),
}


def match_trigger_masks(
    masks,
    *,
    event_bits: Iterable[int],
    channel: int,
    routing: Literal["standard", "aZw", "aZx"] = "standard",
) -> str | None:
    """Return apply/remove for a verified native channel-mask intersection.

    Routing selects native eZR.aZw/aZx branches; actor/source filtering,
    bypass flags, recursion suppression and conditions must be validated
    before this matcher. aZO (index6) contains emitted bits, not subscriptions.
    """
    valid = {
        "standard": {1, 2, 3, 4, 5, 6},
        "aZw": {10, 20, 30, 40, 60},
        "aZx": {11, 21, 31, 41, 61},
    }
    if routing not in valid or channel not in valid[routing]:
        raise UnknownTriggerRouting(
            f"Unsupported native channel {channel} for {routing}"
        )
    if len(masks) != 7:
        raise UnknownTriggerRouting("Seven native PK masks required")
    bits = frozenset(event_bits)
    if any(type(bit) is not int or bit < 0 for bit in bits):
        raise ValueError("Native event bits must be nonnegative integers")
    index, action = _CHANNELS[channel]
    selected = masks[index]
    return action if selected is not None and bits.intersection(selected) else None


@dataclass(frozen=True)
class TriggerSubscription:
    instance_id: int
    effect_id: int
    owner_id: int
    masks: tuple[frozenset[int] | None, ...]
    priority: int = 0
    routing: Literal["standard", "aZw", "aZx"] = "standard"


@dataclass(frozen=True)
class TriggerDispatch:
    subscription: TriggerSubscription
    action: Literal["apply", "remove"]


def plan_trigger_dispatch(
    subscriptions: Iterable[TriggerSubscription],
    *,
    owner_id: int,
    event_bits: Iterable[int],
    channel: int,
    routing: Literal["standard", "aZw", "aZx"] = "standard",
    excluded_instance_ids: frozenset[int] = frozenset(),
) -> tuple[TriggerDispatch, ...]:
    """Pure plan after caller verifies native source guards.

    eZX removes first, then sorts applications using eZY: priority descending,
    effect ID ascending, instance ID ascending. Snapshot plans permit handlers
    to alter their live registry without changing the pending candidate list.
    """
    bits = tuple(event_bits)
    matches = []
    for subscription in tuple(subscriptions):
        if (
            subscription.owner_id != owner_id
            or subscription.routing != routing
            or subscription.instance_id in excluded_instance_ids
        ):
            continue
        action = match_trigger_masks(
            subscription.masks, event_bits=bits, channel=channel, routing=routing
        )
        if action:
            matches.append(TriggerDispatch(subscription, action))
    removals = [item for item in matches if item.action == "remove"]
    applications = sorted(
        (item for item in matches if item.action == "apply"),
        key=lambda item: (
            -item.subscription.priority,
            item.subscription.effect_id,
            item.subscription.instance_id,
        ),
    )
    return tuple(removals + applications)
