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
    from .combat_encounter_scene_helpers import scene_helper_controller_records
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
    bootstrap_effects_by_actor = {}
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
        # Native13912 does not execute649. Its exact retained carrier owns
        # construction after ACTION and the final manager reset.
        bootstrap_effects = grant_projection.effects(actor.id, effects)
        if actor.id in birth_ids:
            continue  # Its exact birth enrolls the actor, once, after bootstrap.
        bootstrap_effects_by_actor[actor.id] = bootstrap_effects
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
    marker_packets = ()
    canonical_marker = False
    witness_counter = fight.turn_id
    if birth_ids:
        if runtime.awaiting_ack is not None:
            if shared.ack.turn != runtime.awaiting_ack:
                raise ValueError("Owned reconnect has inconsistent native ACK boundary")
            marker_packets = getattr(shared, "reconnect_turn_end_packets", ())
            if not marker_packets:
                raise ValueError("Owned reconnect lacks original turn-end presentation")
            witness_counter = runtime.awaiting_ack
            canonical_marker = True
        else:
            history = getattr(shared, "reconnect_end_turn_history", None)
            if history is not None:
                counter, original = history
                initial_ids = {row["actor_id"] for row in participants}
                marker_ids = {
                    struct.unpack_from(">q", body, 12)[0]
                    for opcode, body in original
                    if opcode == 12502 and len(body) == 28
                }
                if marker_ids and marker_ids <= initial_ids:
                    witness_counter, marker_packets = counter, original
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
            initial_summon_timeline(fight, birth_ids, counter=witness_counter)
            if birth_ids
            else current_timeline
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
    def recovery_packet(state):
        envelope = struct.pack(">BBiBh", 1, 0, 6, 0, len(state)) + state
        return 12053, struct.pack(">ih", fight.id, len(envelope)) + envelope

    # Establish ACTION over the INITIAL baseline before any birth or649 can
    # construct a temporary shortcut. The later cvn restores SU in place;
    # its native consumer preserves ACTION and the actual actor controllers.
    packets = [
        (12847, bootstrap(value)),
        (12233, struct.pack(">i", fight.id)),
        # Native bvY.a(cNT) marks the UI started only when SU already runs.
        # Start the exact bootstrap baseline before ACTION binds that widget;
        # otherwise later initiative hydration can sort an ongoing timeline
        # through cNT.a(PA) as though it still belonged to placement. The full
        # authoritative SU remains behind the genuine birth witness below.
        recovery_packet(value["myG"]),
        action_transition(
            fight.id,
            controller_records=scene_helper_controller_records(fight),
        ),
    ]
    packets.extend(birth_packets)
    if birth_packets:
        # Closing starts an asynchronous group; only its real end-turn witness
        # may release the destructive SU/manager continuation below.
        packets.append((13420, struct.pack(">i", fight.id)))
    resume_start = len(packets)
    packets.append(recovery_packet(current_timeline))
    # ACTION must bind the controller before the deferred649 carriers.
    for identity, (stats, effects) in payloads.items():
        final_effects = grant_projection.effects(identity, effects, final=True)
        # big.dU (13912) destructively resets every characteristic and invokes
        # its observers. The bootstrap already installed this exact effect
        # snapshot; resetting it again can invalidate native one-shot observers.
        # Birth actors have no bootstrap snapshot and still require restoration.
        if bootstrap_effects_by_actor.get(identity) != final_effects:
            packets.append(
                (
                    13912,
                    actor_state(13912, fight.id, identity, final_effects),
                )
            )
        packets.append((12873, actor_state(12873, fight.id, identity, stats)))
    grant_projection.verify_complete(final=True)
    packets.extend(grant_projection.grant_carriers)
    packets.extend(grant_projection.other_carriers)
    from .combat_death_script_snapshot import immediate_death_script_packets

    packets.extend(
        immediate_death_script_packets(
            fight,
            (actor for actor in fight.actors.values() if actor.id not in departed),
            runtime.native_action_id,
        )
    )
    if grant_projection.grant_carriers or grant_projection.other_carriers:
        packets.append((13420, struct.pack(">i", fight.id)))
    if birth_ids:
        from .combat_reconnect_birth_stage import (
            BirthPresentation,
            StagedReconnectPackets,
        )
        from .ecology_feedback import information

        presentation = BirthPresentation(
            counter=witness_counter,
            actor_ids=tuple(sorted(birth_ids)),
            resume_packets=tuple(packets[resume_start:]),
            marker_packets=tuple(marker_packets),
            canonical_marker=canonical_marker,
        )
        prefix = packets[:resume_start] + list(marker_packets)
        prefix.append(
            information(
                "Recuperando el combate y las invocaciones. "
                "Espera la sincronización; si acaba de comenzar, espera que termine el turno."
            )
        )
        return StagedReconnectPackets(prefix, presentation)
    if runtime.awaiting_ack is not None:
        if shared.ack.turn != runtime.awaiting_ack:
            raise ValueError("Owned reconnect has inconsistent native ACK boundary")
        if session.account_id not in shared.ack.received:
            presentation = getattr(shared, "reconnect_turn_end_packets", None)
            if not presentation:
                raise ValueError("Owned reconnect lacks original turn-end presentation")
            packets.extend(presentation)
    return tuple(packets)
