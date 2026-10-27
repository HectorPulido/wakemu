"""Source-qualified external boundaries for actual owned equipment descendants.

The installed native consumers define event1004 as the end of a timeline round.
The original server publisher is unavailable. Queueing the completed SU cycle
and replaying it before next-start reactions is explicit Wakemu policy. Existing
equipment contracts retain their source scope; ordinary NPC-source consumers
share only these same reconstructed round/wave boundaries.
"""

ROUND_POLICY = "wakemu.equipment.completed-su-round-v1"


def preflight(factory, retained_container):
    from .combat_equipment_retained_lifecycle import preflight as retained

    return retained(factory, retained_container)


def _has_equipment_sources(fight):
    # Full Ready also records successful empty equipment initialization.
    # Such a receipt does not establish any item-owned event listener.
    initialized = getattr(fight, "native_owned_equipment_initializations", None) or {}
    return any(marker.get("sources") for marker in initialized.values())


def qualified_uids(dispatcher):
    """Reuse original item custody and its complete retained descendant closure."""
    from .combat_equipment_finish import _qualified_sources, _scope

    fight = dispatcher.native_retention.fight
    if not _has_equipment_sources(fight):
        return frozenset()
    entries = tuple(dispatcher.native_retention.view().entries)
    return _scope(fight, entries, _qualified_sources(fight))


def deliver_scoped_pairs(
    dispatcher,
    *,
    event_id,
    recipients,
    npc_sources=False,
    equipment_actor_ids=None,
    excluded_uids=frozenset(),
):
    """Route actual participant roles, never every actor's local notification.

    Rebuild the descendant closure after each synchronous callback. Native Qf
    still owns its per-delivery snapshot, priorities and activation/removal.
    """
    from .combat_event_replay import NativeExternalEvent

    if excluded_uids and event_id != 1004:
        raise ValueError("Source clock exclusions require the exact round event")
    if npc_sources and event_id not in (1004, 1048):
        raise ValueError("NPC source scope requires its round/wave boundary")

    outcomes = []
    for identity, channel in recipients:
        eligible = (
            qualified_uids(dispatcher)
            if equipment_actor_ids is None or identity in equipment_actor_ids
            else frozenset()
        )
        if npc_sources:
            from .combat_npc_external_event_scope import qualified_npc_uids

            eligible |= qualified_npc_uids(dispatcher)
        eligible -= excluded_uids
        if not eligible:
            continue
        outcomes.extend(
            dispatcher.replay_event(
                NativeExternalEvent(identity, (event_id,), channel),
                authority=dispatcher.native_clone_authority,
                eligible_uids=eligible,
            )
        )
    return tuple(outcomes)


def queue_completed_round(fight):
    """Called by actual _advance immediately before the native SU wrap."""
    if not getattr(fight, "native_start_event_delivered", False):
        return
    if not _has_equipment_sources(fight):
        from .combat_npc_external_event_scope import has_npc_round_interest

        if not has_npc_round_interest(fight):
            from .combat_spirit_round_events import has_round_interest

            if not has_round_interest(fight):
                return
    if (
        fight.phase != "active"
        or fight.current is None
        or any(
            fight._in_play(fight.actors[uid])
            for uid in fight.order[fight.turn_index + 1 :]
        )
        or type(fight.native_timeline_round) is not int
        or fight.native_timeline_round < 1
    ):
        raise ValueError(
            "Equipment round boundary requires a completed native SU cycle"
        )
    receipt = dict(
        policy=ROUND_POLICY,
        completed_round=fight.native_timeline_round,
        ending_turn=fight.turn_id,
        ending_actor=fight.current.id,
        delivered=False,
    )
    receipts = getattr(fight, "native_equipment_completed_rounds", None)
    if receipts is None:
        receipts = fight.native_equipment_completed_rounds = {}
    key = str(fight.native_timeline_round)
    previous = receipts.get(key)
    if previous is not None and previous != receipt:
        raise ValueError("Completed equipment round receipt changed")
    receipts.setdefault(key, receipt)


def deliver_completed_round(dispatcher):
    """Consume one checkpoint-owned completed round before next1001 reactions."""
    fight = dispatcher.native_retention.fight
    receipts = getattr(fight, "native_equipment_completed_rounds", {})
    receipt = receipts.get(str(fight.native_timeline_round - 1))
    if receipt is None or receipt.get("delivered") is True:
        return ()
    if (
        receipt.get("policy") != ROUND_POLICY
        or receipt.get("completed_round") != fight.native_timeline_round - 1
        or receipt.get("ending_turn") != fight.turn_id - 1
        or receipt.get("ending_actor") not in fight.actors
        or fight.phase != "active"
        or fight.current is None
    ):
        raise ValueError("Equipment round receipt differs from actual completed cycle")
    from .combat_global_pv_collections import global_pv_iterator
    from .combat_state_managers import registered_area_pv

    managers = []
    for identity in global_pv_iterator(fight, caster_id=receipt["ending_actor"]):
        if identity not in fight.actors:
            area = registered_area_pv(fight, identity)
            if area is None:
                raise ValueError(
                    "Equipment round observer lacks its actual native manager"
                )
            if not area.native_running_effect_manager:
                continue
        managers.append(identity)
    pairs = tuple((identity, channel) for identity in managers for channel in (6, 60))
    pairs += tuple((identity, 61) for identity in managers)
    from .combat_spirit_round_events import (
        prepare_scope,
        deliver_completed_round as deliver_spirit_round,
    )

    spirit_scope = prepare_scope(dispatcher)
    excluded = (
        spirit_scope["eligible_uids"] if spirit_scope is not None else frozenset()
    )
    # Set before callbacks to reject recursion; a failed owned preview discards
    # this marker and its outbox together. Committed checkpoint retries are no-op.
    receipt["delivered"] = True
    outcomes = deliver_scoped_pairs(
        dispatcher,
        event_id=1004,
        recipients=pairs,
        npc_sources=True,
        excluded_uids=excluded,
    )
    from .combat_external_event_removal import (
        has_removal_subscription,
        removal_recipients,
    )

    spirit_pairs = pairs
    if has_removal_subscription(dispatcher, 1004):
        removals = removal_recipients(pairs)
        spirit_pairs += tuple(removals)
        outcomes += deliver_scoped_pairs(
            dispatcher,
            event_id=1004,
            recipients=removals,
            npc_sources=True,
            excluded_uids=excluded,
        )
    outcomes += deliver_spirit_round(dispatcher, receipt, spirit_pairs, spirit_scope)
    return outcomes
