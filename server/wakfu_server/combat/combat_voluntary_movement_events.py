"""Wakemu event1005 policy for a successful voluntary movement step.

Native consumers combine1005 with forced movement185 and teleport2224;
standard bearer398802 removes its stationary state on1005. The original
server publisher is unavailable. Step timing and null-source delivery are
explicit server policy, independent of damage, push and teleport events.
"""
from .combat_event_replay import NativeExternalEvent


def deliver_voluntary_movement(dispatcher, *, actor_id, from_cell, to_cell, action_id):
    fight = dispatcher.native_retention.fight
    actor = fight.actors.get(actor_id)
    if actor is None or tuple(actor.position) != tuple(to_cell):
        raise ValueError("Voluntary movement requires the actual moved fighter")
    if tuple(from_cell) == tuple(to_cell):
        return ()
    from .combat_global_pv_collections import global_pv_iterator
    from .combat_state_managers import registered_area_pv

    recipients = [(actor_id, channel) for channel in (6, 60, 4, 40)]
    for identity in global_pv_iterator(fight, caster_id=actor_id):
        if identity not in fight.actors:
            area = registered_area_pv(fight, identity)
            if area is None:
                raise ValueError("Movement observer lacks its native PV manager")
            if not area.native_running_effect_manager:
                continue
        recipients.extend((identity, channel) for channel in (61, 41))
    from .combat_encounter_table_listeners import frozen_table_listener_policy

    frozen = frozen_table_listener_policy(fight)
    calendar_callbacks = (
        tuple(
            row
            for row in frozen.get("callbacks", ())
            if row["timing"] == "owned_boss_post_start" and row["event_id"] == 1005
        )
        if frozen is not None
        else ()
    )
    outcomes = []
    from .combat_external_movement_recipient import (
        POLICY,
        committed_movement_recipient_scope,
    )

    context = dict(
        policy=POLICY,
        actor_id=actor_id,
        turn_id=fight.turn_id,
        action_id=action_id,
        from_cell=tuple(from_cell),
        to_cell=tuple(to_cell),
        event_id=1005,
    )
    from .combat_gate_movement_boundary import current_gate_movement_boundary

    gate = current_gate_movement_boundary(fight, actor_id, from_cell, to_cell)
    if gate is not None:
        context["gate_boundary"] = gate.facts()
    from .combat_hour_travel import current_hour_movement_boundary

    hour = current_hour_movement_boundary(fight, actor_id, from_cell, to_cell)
    if hour is not None:
        context["hour_boundary"] = dict(hour)
    with committed_movement_recipient_scope(fight, context):
        for identity, channel in recipients:
            replay_options = {}
            relevant_callbacks = tuple(
                row for row in calendar_callbacks if row["channel"] == channel
            )
            if relevant_callbacks:
                entries = tuple(dispatcher.native_retention.view().entries)
                excluded = set()
                manager = fight.actors.get(identity)
                receipt = getattr(fight, "native_npc_initialization_receipts", {}).get(
                    identity, {}
                )
                for callback in relevant_callbacks:
                    if (
                        manager is None
                        or receipt.get("ref") != callback["owner_reference"]
                    ):
                        continue
                    carriers = {
                        state.uid
                        for state in manager.state_ledger.entries
                        if state.reference == callback["owner_state"]
                        and state.caster_id == identity
                        and state.target_id == identity
                    }
                    for entry in entries:
                        if (
                            entry.manager_id != identity
                            or entry.generic_effect != callback["effect_reference"]
                        ):
                            continue
                        original = (
                            getattr(fight, "native_owned_group_effects", {})
                            .get(entry.uid, {})
                            .get("invocation", {})
                        )
                        if (
                            original.get("reference") == callback["effect_reference"]
                            and original.get("state_uid") in carriers
                            and original.get("caster_id") == identity
                            and original.get("target_id") == identity
                        ):
                            excluded.add(entry.uid)
                if excluded:
                    replay_options["eligible_uids"] = frozenset(
                        entry.uid for entry in entries if entry.uid not in excluded
                    )
            outcomes.extend(
                dispatcher.replay_event(
                    NativeExternalEvent(
                        identity, (1005,), channel, movement_boundary_context=context
                    ),
                    authority=dispatcher.native_clone_authority,
                    **replay_options,
                )
            )
    return tuple(outcomes)
