"""Area event producers and the frozen Qs movement delivery contract.

Subscriptions are native BitSets, not producer declarations. In particular a
definition subscribing to 10016 does not authorize an external event10016.
The movement plan captures actual Qq objects before any callback runs; it must
not resolve an identity again after an earlier callback removes that object.
"""
from dataclasses import dataclass
from types import MappingProxyType

from .combat_effect_area_geometry import contains_area_actor, contains_area_cell
from .combat_area_contracts import AREA_CONTRACTS


@dataclass(frozen=True)
class AreaEventProducer:
    name: str
    event_ids: tuple
    authority: str
    timing: str


AREA_EVENT_PRODUCERS = MappingProxyType(
    {
        "movement": AreaEventProducer(
            "movement",
            (10001, 10008, 10002),
            "Qs frozen actual-object lists",
            "after registered relocation, before displacement completion phases",
        ),
        "turn_start": AreaEventProducer(
            "turn_start",
            (10000,),
            "Wakemu installed glyph policy",
            "current active fighter turn-start boundary",
        ),
        "removal": AreaEventProducer(
            "removal",
            (10011,),
            "Qs unregister then faV callback",
            "after area unregistration, before parent removal completes",
        ),
        "running_source": AreaEventProducer(
            "running_source",
            (),
            "actual Qe definition mask6, channel1",
            "after the actual recipient Qf delivery",
        ),
    }
)

MOVEMENT_AREA_EVENT_ORDER = AREA_EVENT_PRODUCERS["movement"].event_ids


@dataclass(frozen=True)
class AreaEventConsumer:
    family: str
    native_class: str
    adapter: str
    mask_authority: str


# This is a compatibility registration, not a replacement implementation of
# subclass guards. NativeAreaEventRuntime._deliver_event continues to own
# owner/affiliation/reentrancy/charge/retirement rules for these actual Qq kinds.
AREA_EVENT_CONSUMERS = MappingProxyType(
    {
        native_class: AreaEventConsumer(
            family,
            native_class,
            "NativeAreaEventRuntime._deliver_event",
            "native entry_masks, exit_masks, native_removal_masks",
        )
        for family, native_class in AREA_CONTRACTS.items()
    }
)


@dataclass(frozen=True)
class AreaMovementDelivery:
    event_id: int
    # These are the original objects, deliberately not copies or UID lookups.
    recipients: tuple


def plan_area_movement(rows, definition_for, target, *, from_cell, to_cell):
    """Freeze native entry/inside/exit lists without invoking a consumer.

    The origin is tested as a point and the destination with the actor's native
    physical radius. This asymmetry is intentional; the generic external event
    route has its own point containment contract and must not use this planner.
    Definition validation runs in the original area traversal order."""
    groups = {event_id: [] for event_id in MOVEMENT_AREA_EVENT_ORDER}
    for row in rows:
        definition = definition_for(row)
        before = contains_area_cell(row, from_cell)
        after = contains_area_actor(row, to_cell, target.physical_radius)
        event_id = (
            (10008 if before else 10001) if after else (10002 if before else None)
        )
        if event_id is not None:
            groups[event_id].append((row, definition))
    return tuple(
        AreaMovementDelivery(event_id, tuple(groups[event_id]))
        for event_id in MOVEMENT_AREA_EVENT_ORDER
    )


def deliver_area_movement(plan, target, deliver_event):
    """Preserve each event group's result and callback order, including empties."""
    return tuple(
        tuple(
            outcome
            for row, definition in delivery.recipients
            for outcome in deliver_event(row, definition, target, delivery.event_id)
        )
        for delivery in plan
    )
