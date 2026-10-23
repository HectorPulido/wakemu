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
        ),
    }
    from .combat_finisher_events import prepare_owned_finisher

    finisher = prepare_owned_finisher(fight, source, replay=replay, authority=authority)
    if finisher is not None:
        if not callable(finisher_cleanup):
            raise ValueError("Finisher requires post-delivery cleanup boundary")
        finisher_cleanup(finisher)
        fight.native_death_event_deliveries[sequence][
            "finisher_policy"
        ] = "wakemu.owned-finisher-boundaries-v1"
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
    outcomes.extend(replay(replace(source, event_ids=(1010,)), authority=authority))
    for event_id in (1010, 1012):
        if hasattr(fight, "native_global_pv_collections"):
            from .combat_global_pv_collections import global_pv_iterator
            from .combat_state_managers import registered_area_pv

            # Reacquire native topology after the preceding event's callbacks.
            # Each iterator preserves its own mutation-aware native PV order.
            for identity in global_pv_iterator(fight, caster_id=source.caster_id):
                if identity not in fight.actors:
                    manager = registered_area_pv(fight, identity)
                    if manager is None:
                        raise ValueError("KO/death event global PV manager absent")
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
    return tuple(outcomes)
