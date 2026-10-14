"""Wakemu policy: start detached finite state clocks at the first real SU.

The detached native constructor has no SU and keeps timer=None. Native
post-registration migration equivalence is unproved. This explicit integration
policy starts the original duration once actual combat registration exists;
it never removes a state, grants resources, or reapplies its child effects.
"""
from dataclasses import replace


def bind_initial_finite_clocks(fight, catalog=None):
    from .combat_native_timing_context import native_time_payload
    from .combat_state_timing import StateTimingDefinition, schedule_state_timer
    from wakfu_server.wire import proto_fields, proto_field

    if fight.phase != "active" or fight.current is None:
        return ()
    order = tuple(fight.order)
    if len(set(order)) != len(order) or fight.current.id not in order:
        raise ValueError("Missing real registered finite-clock timeline")
    provenance = {
        identity
        for identity, row in getattr(
            fight, "native_npc_initialization_receipts", {}
        ).items()
        if row.get("initialized") is True
    }
    provenance.update(
        identity
        for identity, row in getattr(fight, "native_summon_registrations", {}).items()
        if row.get("actor_id") == identity
    )
    changes = []
    for identity in order:
        actor = fight.actors[identity]
        if identity not in provenance:
            continue
        for entry in actor.state_ledger.entries:
            if (
                entry.timer is not None
                or entry.duration <= 0
                or entry.protected is not False
                or entry.realtime_duration != 0
            ):
                continue
            if catalog is None:
                from .combat_server_spell import states_catalog

                catalog = states_catalog()
            definition = catalog["states"].get(str(entry.reference))
            if definition is None or definition.get("skip_turn_timer") is not False:
                continue
            timing = StateTimingDefinition(
                definition["duration_base"],
                definition["duration_per_level"],
                definition["maximum_level"],
                definition["tick_at_turn_end"],
                definition["clock_actor"] == "caster",
                False,
            )
            if timing.duration(entry.level) != entry.duration:
                raise ValueError(
                    "Constructor finite state differs from native duration"
                )
            clock_id = entry.caster_id if timing.clock_on_caster else entry.target_id
            if clock_id not in order:
                raise ValueError("Missing registered constructor state clock actor")
            timer = schedule_state_timer(
                timing,
                level=entry.level,
                caster_id=entry.caster_id,
                target_id=entry.target_id,
                round_number=fight.native_timeline_round,
                current_actor_id=fight.current.id,
                current_actor_index=fight.turn_index,
                clock_actor_index=order.index(clock_id),
                current_phase="active",
            )
            if timer is None:
                raise ValueError("Finite registration policy did not produce a timer")
            payload = bytes.fromhex(fight.state_wire_payloads[entry.uid])
            fields = list(proto_fields(payload))
            if sum(tag == 90 for tag, _ in fields) != 1:
                raise ValueError("Missing unique constructor carrier TimeDatas")
            replacement = b"".join(
                proto_field(
                    tag,
                    native_time_payload(
                        timer, realtime_remaining=entry.realtime_duration
                    )
                    if tag == 90
                    else value,
                )
                for tag, value in fields
            )
            changes.append(
                (actor, entry, replace(entry, timer=timer), replacement.hex())
            )
    # All clocks and wire records validate before publishing any changed entry.
    for actor, entry, updated, payload in changes:
        actor.state_ledger.bind_registered_timer(entry, updated)
        fight.state_wire_payloads[entry.uid] = payload
    return tuple(entry.uid for _, entry, _, _ in changes)
