"""Read-only owned reconnect presentation of the current shared fight.

The bootstrap restores client objects. Retained carriers are installed without
executing children; the server FSM, ACK barrier and resource ledger stay intact.
"""
from .combat_environment_glyphs import environment_sections
import struct
import time


def owned_snapshot(fight, shared, session, *, actor_payload):
    if fight.phase == "placement":
        from .combat_session_adapter import CombatSessionAdapter

        return CombatSessionAdapter.placement_bootstrap(fight, shared, session)
    if fight.phase != "active" or shared.runtime is None:
        raise ValueError("Owned reconnect requires a live native combat phase")
    context = shared.join_context
    required = {"arena", "terrain_effect_id", "terrain_instance_id", "leaders"}
    if not isinstance(context, dict) or required - context.keys():
        raise ValueError("Owned reconnect lacks native fight bootstrap context")
    from .combat_recovery import timeline
    from .combat_phase import action_transition
    from .combat_spectator_snapshot import _retained_carrier_packets
    from .combat_wire import bootstrap, topology, actor_state

    runtime = shared.runtime
    deadline = runtime.turn_deadline
    # An ACK-paused turn has no running deadline. Preserve that pause, while
    # presenting its actual current member; no timer is armed by this snapshot.
    paused = getattr(shared, "reconnect_remaining_turn_seconds", None)
    remaining = (
        paused
        if paused is not None
        else 0
        if deadline is None
        else max(0, deadline - runtime.clock())
    )
    deadline_ms = int(time.time() * 1000 + remaining * 1000)
    current_timeline = timeline(fight, deadline_ms=deadline_ms)
    participants = []
    payloads = {}
    for actor in fight.actors.values():
        stats, effects = actor_payload(fight, actor, session)
        payloads[actor.id] = (stats, effects)
        participants.append(
            dict(
                actor_id=actor.id,
                myB=0 if actor.controlled else 1,
                myn=actor.team,
                myC=1,
                myE=stats,
                myF=effects,
            )
        )
    value = dict(
        fight_id=fight.id,
        kind=getattr(fight, "native_fight_model", None),
        bqh=shared.map_id,
        myo=context["terrain_effect_id"],
        myp=context["terrain_instance_id"],
        myD=topology(context["arena"]),
        myG=current_timeline,
        myI=context["leaders"][0],
        myJ=context["leaders"][1],
        compact=False,
        participants=participants,
        myH=[],
        myM=[],
        myN=[],
        myK=environment_sections(fight),
    )
    # cvb owned fight creation, followed by the existing native phase transition
    # contract and cvn recovery. Never use spectator cva/12044 for an owner.
    recovery = (
        struct.pack(">BBiBh", 1, 0, 6, 0, len(current_timeline)) + current_timeline
    )
    packets = [(12847, bootstrap(value))]
    registrations = getattr(fight, "native_summon_registrations", {})
    births = getattr(fight, "native_summon_creation_deliveries", {})
    for identity in registrations:
        if identity not in fight.actors:
            continue
        birth = births.get(identity)
        if (
            not isinstance(birth, dict)
            or type(birth.get("opcode")) is not int
            or not isinstance(birth.get("payload_hex"), str)
        ):
            raise ValueError("Owned reconnect lacks actual summon creation payload")
        packets.append((birth["opcode"], bytes.fromhex(birth["payload_hex"])))
    # Restore current PA and retained remote-effect state after creation. These
    # are snapshot streams, never the gameplay effect dispatcher.
    for identity, (stats, effects) in payloads.items():
        packets.extend(
            (
                (13912, actor_state(13912, fight.id, identity, effects)),
                (12873, actor_state(12873, fight.id, identity, stats)),
            )
        )
    packets.extend(
        (
            (12233, struct.pack(">i", fight.id)),
            action_transition(fight.id),
            (12053, struct.pack(">ih", fight.id, len(recovery)) + recovery),
        )
    )
    packets.extend(_retained_carrier_packets(fight, runtime.native_action_id))
    from .combat_death_script_snapshot import immediate_death_script_packet

    for actor in fight.actors.values():
        immediate = immediate_death_script_packet(
            fight, actor, runtime.native_action_id
        )
        if immediate is not None:
            packets.append(immediate)
    if runtime.awaiting_ack is not None:
        if shared.ack.turn != runtime.awaiting_ack:
            raise ValueError("Owned reconnect has inconsistent native ACK boundary")
        if session.account_id not in shared.ack.received:
            presentation = getattr(shared, "reconnect_turn_end_packets", None)
            if not presentation:
                raise ValueError("Owned reconnect lacks original turn-end presentation")
            packets.extend(presentation)
    return tuple(packets)
