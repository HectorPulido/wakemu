"""Native L4 selection at separately established owned external boundaries.

These helpers do not publish an event or invent its owner. A producer supplies
its actual event and frozen native recipient order. Applied scalar runners may
have only a removal mask; they are not deferred activation listeners.
"""
from collections.abc import Mapping
from types import SimpleNamespace


def applied_removal_contract(dispatcher, retention, entry):
    """Read one actual applied runner's masks from its immutable definition."""
    fight = retention.fight
    row = getattr(fight, "owned_stat_effects", {}).get(entry.uid)
    if row is None:
        return None
    effects = getattr(dispatcher, "effects", None)
    effect = None if effects is None else effects.get(str(entry.generic_effect))
    if not isinstance(effect, Mapping):
        raise ValueError("Applied removal requires its original effect definition")
    masks = effect.get("target_masks")
    if not isinstance(masks, (list, tuple)) or len(masks) != 7:
        raise ValueError("Applied removal requires seven native masks")
    if not masks[2]:
        return None
    definition = retention.definition(
        effect, SimpleNamespace(reference=entry.generic_effect)
    )
    if (
        definition["subscription"] is not False
        or row.get("effect_class") != entry.effect_class
        or definition["effect_class"] != entry.effect_class
    ):
        raise ValueError("Applied removal differs from the retained scalar runner")
    flags = effect.get("native_effect_flags")
    if not isinstance(flags, (list, tuple)) or any(
        type(flag) is not int for flag in flags
    ):
        raise ValueError("Applied removal requires original native effect flags")
    return masks, flags, definition


def has_removal_subscription(dispatcher, event_id):
    """Cheap live interest check; replay still validates complete Qf authority."""
    if type(event_id) is not int or event_id < 0:
        raise ValueError("Native removal event ID required")
    retention = dispatcher.native_retention
    fight = retention.fight
    for row in getattr(fight, "native_owned_group_effects", {}).values():
        masks = row.get("native_subscription_masks")
        if (
            isinstance(masks, (list, tuple))
            and len(masks) == 7
            and event_id in (masks[2] or ())
        ):
            return True
    effects = getattr(dispatcher, "effects", None)
    if effects is None:
        return False
    # Records identify original definitions without decoding payloads or making
    # a complete retained view merely to determine whether L4 has any listener.
    records = getattr(fight, "native_retained_records", {})
    for uid in getattr(fight, "owned_stat_effects", {}):
        record = records.get(uid)
        if not isinstance(record, Mapping):
            continue  # The real replay, if needed, retains its full-view guard.
        effect = effects.get(str(record["generic_effect"]))
        masks = None if effect is None else effect.get("target_masks")
        if (
            isinstance(masks, (list, tuple))
            and len(masks) == 7
            and event_id in (masks[2] or ())
        ):
            return True
    return False


def removal_recipients(recipients):
    """Map the producer's actual L6 order to corresponding native L4 managers."""
    result = []
    channels = {6: 4, 60: 40, 61: 41}
    for actor_id, channel in recipients:
        if (
            type(actor_id) is not int
            or actor_id == 0
            or type(channel) is not int
            or channel not in channels
        ):
            raise ValueError("Owned external recipient identity/channel required")
        result.append((actor_id, channels[channel]))
    return tuple(result)
