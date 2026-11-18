"""Owned death boundaries using native local/global Qf subscriptions.

Installed state7128 listener326382 subscribes Qa.aZL()/beD=[1013], mask5.
The original server producer is unavailable: local channel6, the lethal running source, after OFF_PLAY
and before reconciliation is an explicit Wakemu policy. No reversed/global
delivery is inferred from the local subscription. Listener326382 compares
GetEffectCaster() with GetTriggeringEffectCaster(): a null-source boundary
would erase the actual killer and cannot satisfy that original contract.
Global1012 additionally serves the original Moon6175 listener293426. Its
channel61 delivery after global1010 and before local1013 is a consumer-backed
Wakemu reconstruction, not a recovered original server caller.
"""
from dataclasses import replace
from .combat_event_replay import NativeEventSource

_CONVOY_ROUTE = "quest-map-947-25104-2199"
_CONVOY_CARRIERS = {
    "wakemu.kelba.native-cargo-stage-1.v1": (1, 3589),
    "wakemu.kelba.native-cargo-stage-2.v1": (2, 3711),
}


def _convoy_last_ally_reaction(fight, source, *, replay, authority):
    """Deliver the pinned convoy's 3478/152002 listener on the last allied KO."""
    record = getattr(fight, "native_encounter_scene", None)
    if (
        fight.phase != "active"
        or record is None
        or record["scope"]["route_key"] != _CONVOY_ROUTE
    ):
        return ()
    from .combat_encounter_scene_policy import _verified

    record = _verified(record)
    scope, descriptor = record["scope"], record["descriptor"]
    policy = _CONVOY_CARRIERS.get(descriptor["policy_id"])
    if policy is None or scope["map_id"] != 947 or scope["room_order"] != policy[0]:
        return ()
    bindings = {row["actor_id"]: row["ref"] for row in scope["actor_bindings"]}
    carriers = [identity for identity, ref in bindings.items() if ref == policy[1]]
    if len(carriers) != 1:
        raise ValueError("Convoy death reaction requires its bound carrier")
    carrier_id = carriers[0]
    if source.target_id == carrier_id or source.target_id not in bindings:
        return ()

    carrier = fight.actors.get(carrier_id)
    if carrier is None or not fight._in_play(carrier):
        return ()
    # The frozen bindings contain only this convoy's initial NPCs. The
    # retained listener independently checks the complete native ally count,
    # including any later summons and its property exclusions.
    if any(
        (actor := fight.actors.get(identity)) is not None and fight._in_play(actor)
        for identity in bindings
        if identity != carrier_id
    ):
        return ()
    owned_states = getattr(fight, "native_owned_state_containers", {})
    listeners = frozenset(
        uid
        for uid, row in getattr(fight, "native_owned_group_effects", {}).items()
        if row["target_id"] == carrier_id
        and row["invocation"]["caster_id"] == carrier_id
        and row["invocation"]["reference"] == 152002
        and (state := owned_states.get(row["state_uid"])) is not None
        and state["reference"] == 3478
        and state["caster_id"] == state["target_id"] == carrier_id
    )
    if len(listeners) != 1:
        return ()
    from .combat_external_read_pass import external_recipient_read

    with external_recipient_read(fight, carrier_id, replay):
        return replay(
            replace(source, event_ids=(1041,), channel=61, manager_actor_id=carrier_id),
            authority=authority,
            eligible_uids=listeners,
        )


def deliver_owned_death(
    fight, actor_id, *, source, replay, authority, retention=None, finisher_cleanup=None
):
    from .combat_ordinary_death import registered_ordinary_death, owned_fighter_guards

    actor = fight.actors.get(actor_id)
    if actor is None or registered_ordinary_death(fight, actor) is not True:
        raise ValueError("Death event requires an actual registered death")
    if owned_fighter_guards(fight, actor) != dict(baF=False, baG=True, baK=False):
        raise ValueError("Death event requires the actual OFF_PLAY manager")
    if (
        not isinstance(source, NativeEventSource)
        or source.target_id != actor_id
        or source.manager_actor_id != actor_id
        or source.channel != 6
        or source.event_ids != (1013,)
    ):
        raise ValueError("Death event requires the actual lethal running effect source")
    source.validate()
    event = next(
        row
        for row in reversed(fight.events)
        if row.get("kind") == "death" and row.get("actor_id") == actor_id
    )
    sequence = str(event["sequence"])
    delivered = getattr(fight, "native_death_event_deliveries", {})
    if sequence in delivered:
        return ()
    # Mark before synchronous replay: nested damage must not duplicate this
    # boundary. Both record and reactions belong to the unpublished preview.
    fight.native_death_event_deliveries = {
        **delivered,
        sequence: dict(
            actor_id=actor_id,
            event_id=1013,
            channel=6,
            policy="wakemu.owned-ko-and-death-v3",
            ko_event_id=1010,
            global_death_event_id=1012,
            source_id=source.caster_id,
            generic_effect=source.generic_effect,
            effect_class=source.effect_action_id,
        ),
    }
    from .combat_owned_area_death import apply_owned_area_death

    # The actual OFF_PLAY transition precedes this callback and settlement.
    # Keep Qs.l's removal effects inside the same private native dispatcher;
    # a presentation-only death packet is too late to change the outcome.
    apply_owned_area_death(fight, actor_id, retention=retention)
    from .combat_finisher_events import prepare_owned_finisher

    finisher = prepare_owned_finisher(fight, source, replay=replay, authority=authority)
    if finisher is not None:
        if not callable(finisher_cleanup):
            raise ValueError("Finisher requires post-delivery cleanup boundary")
        finisher_cleanup(finisher)
        fight.native_death_event_deliveries[sequence][
            "finisher_policy"
        ] = "wakemu.owned-finisher-boundaries-v1"
    from .combat_external_read_pass import external_read_pass

    with external_read_pass(fight, replay, authority, retention):
        return _deliver_death_reactions(fight, source, replay, authority, retention)


def _deliver_death_reactions(fight, source, replay, authority, retention):
    # Consumer-backed Wakemu policy, not a recovered original producer:
    # eZR.bcd recognizes 1010 as a KO context; the 351404 target-code5
    # listener needs the actual defeated PV and lethal caster, not null source.
    outcomes = []
    if source.caster_id is not None:
        outcomes.extend(
            replay(
                replace(
                    source,
                    event_ids=(1010,),
                    channel=60,
                    manager_actor_id=source.caster_id,
                ),
                authority=authority,
            )
        )
    from .rift_ko_cleanup import owned_ko_boundary

    local_ko = replace(source, event_ids=(1010,))
    with owned_ko_boundary(fight, local_ko):
        outcomes.extend(replay(local_ko, authority=authority))
    for event_id in (1010, 1012):
        if hasattr(fight, "native_global_pv_collections"):
            from .combat_external_read_pass import external_global_iterator
            from .combat_state_managers import registered_area_pv

            # Reacquire native topology after the preceding event's callbacks.
            # Each iterator preserves its own mutation-aware native PV order.
            from contextlib import closing

            with closing(
                external_global_iterator(fight, source.caster_id)
            ) as recipients:
                for identity in recipients:
                    from .combat_external_read_pass import external_recipient_read

                    with external_recipient_read(fight, identity, replay):
                        if identity not in fight.actors:
                            manager = registered_area_pv(fight, identity)
                            if manager is None:
                                raise ValueError(
                                    "KO/death event global PV manager absent"
                                )
                            if not manager.native_running_effect_manager:
                                continue
                        outcomes.extend(
                            replay(
                                replace(
                                    source,
                                    event_ids=(event_id,),
                                    channel=61,
                                    manager_actor_id=identity,
                                ),
                                authority=authority,
                            )
                        )
        elif retention is not None:
            from .combat_native_events import subscription_selection

            for entry in retention.view().entries:
                row = fight.native_owned_group_effects.get(entry.uid)
                if row is None:
                    continue
                definition = retention.metadata["effects"][str(entry.generic_effect)]
                if (
                    subscription_selection(
                        masks=row["native_subscription_masks"],
                        event_ids=(event_id,),
                        channel=61,
                        global_subscription=definition["event_global_subscription"],
                        reversed_subscription=definition["event_reverse_subscription"],
                        flags=row["native_effect_flags"],
                        source_present=True,
                    )
                    == "activate"
                ):
                    raise ValueError(
                        "Global KO/death observer requires native PV collection producer"
                    )
        else:
            raise ValueError(
                "KO/death event requires native global collection or subscription authority"
            )
    outcomes.extend(replay(source, authority=authority))
    outcomes.extend(
        _convoy_last_ally_reaction(fight, source, replay=replay, authority=authority)
    )
    return tuple(outcomes)
