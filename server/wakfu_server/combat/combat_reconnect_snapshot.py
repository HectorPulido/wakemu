"""Read-only owned reconnect presentation of the current shared fight.

The bootstrap restores client objects. Retained carriers are installed without
executing children; immediate public PI operands restore their recorded value.
The server FSM, ACK barrier and resource ledger stay intact.
"""
from .combat_environment_glyphs import environment_sections
from .combat_live_area_snapshot import sections as live_area_sections
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
    from .combat_spectator_snapshot import (
        _retained_carrier_packets,
        _project_rehydrated_area_creators,
    )
    from .combat_wire import bootstrap, topology, actor_state
    from .combat_delivery_boundary import initial_summon_timeline

    runtime = shared.runtime
    area_rehydration = {}
    retained_packets = _retained_carrier_packets(
        fight, runtime.native_action_id, area_rehydration=area_rehydration
    )
    from .combat_reconnect_grants import ReconnectGrantProjection

    grant_projection = ReconnectGrantProjection(retained_packets)
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
    from .combat_companions import bootstrap_actor_type

    participants = []
    payloads = {}
    from .combat_snapshot_actor_visibility import hidden_snapshot_actor_ids

    departed = hidden_snapshot_actor_ids(fight)
    registrations = getattr(fight, "native_summon_registrations", {})
    births = getattr(fight, "native_summon_creation_deliveries", {})
    birth_packets = []
    birth_ids = set()
    for identity in registrations:
        if identity not in fight.actors or identity in departed:
            continue
        birth = births.get(identity)
        if (
            not isinstance(birth, dict)
            or type(birth.get("opcode")) is not int
            or not isinstance(birth.get("payload_hex"), str)
        ):
            raise ValueError("Owned reconnect lacks actual summon creation payload")
        birth_packets.append((birth["opcode"], bytes.fromhex(birth["payload_hex"])))
        birth_ids.add(identity)
    for actor in fight.actors.values():
        if actor.id in departed:
            continue
        stats, effects = actor_payload(fight, actor, session)
        # Native Qf.p keeps the first object for a UID. Let the explicit
        # retained carrier own each live eYQ area, rather than admitting an
        # unexecuted duplicate through bootstrap or the later13912 reset.
        effects = _project_rehydrated_area_creators(effects, actor.id, area_rehydration)
        payloads[actor.id] = (stats, effects)
        # Only the final13912 after ACTION constructs649. Keep its complete
        # canonical payload and remote remaining timer, rather than replaying
        # both a snapshot and an evaluated carrier for the same runner.
        bootstrap_effects = grant_projection.effects(actor.id, effects)
        if actor.id in birth_ids:
            continue  # Its exact birth enrolls the actor, once, after bootstrap.
        participants.append(
            dict(
                actor_id=actor.id,
                myB=bootstrap_actor_type(fight, actor),
                myn=actor.team,
                myC=1,
                myE=stats,
                myF=bootstrap_effects,
            )
        )
    grant_projection.verify_complete()
    value = dict(
        fight_id=fight.id,
        kind=getattr(fight, "native_fight_model", None),
        bqh=shared.map_id,
        myo=context["terrain_effect_id"],
        myp=context["terrain_instance_id"],
        myD=topology(context["arena"]),
        # No current-member substitution: INITIAL has the native -1 sentinel.
        # Full recovery below restores real counters and even a summon turn.
        myG=(
            initial_summon_timeline(fight, birth_ids) if birth_ids else current_timeline
        ),
        myI=context["leaders"][0],
        myJ=context["leaders"][1],
        compact=False,
        participants=participants,
        myH=[],
        myM=[],
        myN=[],
        myK=environment_sections(
            fight,
            viewer_id=(
                session.character_id
                if getattr(fight, "native_environment_glyph_constructors", ())
                else None
            ),
        )
        + live_area_sections(fight),
    )
    # cvb owned fight creation, followed by the existing native phase transition
    # contract and cvn recovery. Never use spectator cva/12044 for an owner.
    recovery = (
        struct.pack(">BBiBh", 1, 0, 6, 0, len(current_timeline)) + current_timeline
    )
    # Establish ACTION over the INITIAL baseline before any birth or649 can
    # construct a temporary shortcut. The later cvn restores SU in place;
    # its native consumer preserves ACTION and the actual actor controllers.
    packets = [
        (12847, bootstrap(value)),
        (12233, struct.pack(">i", fight.id)),
        action_transition(fight.id),
    ]
    packets.extend(birth_packets)
    if birth_packets:
        # Close the native creation group before authoritative SU restoration.
        packets.append((13420, struct.pack(">i", fight.id)))
    packets.append((12053, struct.pack(">ih", fight.id, len(recovery)) + recovery))
    # ACTION must bind the controller before649 is executed from13912.
    # big.dU resets frm, so its matching authoritative stats still follow it.
    for identity, (stats, effects) in payloads.items():
        packets.extend(
            (
                (13912, actor_state(13912, fight.id, identity, effects)),
                (12873, actor_state(12873, fight.id, identity, stats)),
            )
        )
    packets.extend(grant_projection.other_carriers)
    from .combat_death_script_snapshot import immediate_death_script_packets

    packets.extend(
        immediate_death_script_packets(
            fight,
            (actor for actor in fight.actors.values() if actor.id not in departed),
            runtime.native_action_id,
        )
    )
    if runtime.awaiting_ack is not None:
        if shared.ack.turn != runtime.awaiting_ack:
            raise ValueError("Owned reconnect has inconsistent native ACK boundary")
        if session.account_id not in shared.ack.received:
            presentation = getattr(shared, "reconnect_turn_end_packets", None)
            if not presentation:
                raise ValueError("Owned reconnect lacks original turn-end presentation")
            packets.extend(presentation)
    return tuple(packets)
