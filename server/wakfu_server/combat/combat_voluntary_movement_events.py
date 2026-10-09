"""Wakemu event1005 policy for a successful voluntary movement step.

Native consumers combine1005 with forced movement185 and teleport2224;
standard bearer398802 removes its stationary state on1005. The original
server publisher is unavailable. Step timing and null-source delivery are
explicit server policy, independent of damage, push and teleport events.
"""
from .combat_event_replay import NativeExternalEvent


def deliver_voluntary_movement(dispatcher, *, actor_id, from_cell, to_cell):
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
    outcomes = []
    for identity, channel in recipients:
        outcomes.extend(
            dispatcher.replay_event(
                NativeExternalEvent(identity, (1005,), channel),
                authority=dispatcher.native_clone_authority,
            )
        )
    return tuple(outcomes)
