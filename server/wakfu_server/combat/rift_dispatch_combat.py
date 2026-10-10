"""Accepted rift action preparation before checkpoint and public delivery."""
import struct
import time

from .combat_shared import Transition


def finish_accepted_action(fight, runtime, packets, *, initialize_actor):
    """Consume a staged wave on a detached accepted preview, without DB writes.

    The caller synchronously checkpoints this result before returning it to the
    shared registry. Native sources live on the preview, never a mutable socket
    context shared with an operation that might still fail.
    """
    from .rift_dispatch_lifecycle import next_roster
    from .rift_npc_creation import install_native_wave
    from .combat_recovery import recovery_packet
    from .combat_phase import action_transition

    state = getattr(fight, "rift_wave_state", None)
    if state is None:
        return Transition(fight, runtime, tuple(packets))
    pending = state.get("pending_wave")
    if fight.phase != "active" or pending is None:
        return Transition(fight, runtime, tuple(packets))
    if runtime is None or runtime.fight is not fight:
        raise ValueError("Rift accepted action has a stale native runtime")
    from .rift_policy import select_wave

    next_refs = select_wave(
        state["catalog"], state["policy"], state["seed"], pending["completed_wave"] + 1
    )
    if len(fight.actors) + len(next_refs) > 127:
        # Native signed-byte roster/history limits are a local implementation
        # boundary, not an official rift win condition or a reward entitlement.
        fight.phase = "finished"
        fight.winner = 1
        state["outcome"] = "capacity_exhausted"
        state["last_cleared_wave"] = dict(pending)
        state["pending_wave"] = None
        fight._event("finished", winner=1, reason="rift_native_history_capacity")
        runtime.pending = []
        runtime.turn_deadline = runtime.deadline_turn = None
        return Transition(fight, runtime, tuple(packets))
    monsters = next_roster(fight, pending)
    sources = getattr(fight, "rift_monsters", None)
    if not isinstance(sources, dict):
        raise ValueError("Rift accepted action lacks ordinary monster sources")
    fight.rift_monsters = {
        **sources,
        **{monster["id"]: monster for monster in monsters},
    }
    added = install_native_wave(fight, monsters, initialize_actor=initialize_actor)
    from .combat_native_action_ids import NATIVE_ACTION_PACKETS

    if 13051 in NATIVE_ACTION_PACKETS:
        added.append(
            (
                13051,
                struct.pack(">iiii", fight.id, runtime.action_id, -1, state["wave"]),
            )
        )
    if runtime.awaiting_ack is not None:
        # Turn-end prepared its next-turn presentation before this admission.
        # Replace that unsent snapshot so ACK cannot restore the old roster.
        runtime.native_initial_timeline_restore_pending = True
        awaiting_ack = runtime.awaiting_ack
        runtime.awaiting_ack = None
        try:
            runtime.pending = runtime.turn_started(arm_deadline=False)
        finally:
            runtime.awaiting_ack = awaiting_ack
    # cYp inserts through native timeline policy. Publish the exact owned SU
    # snapshot afterward to retain the server's explicit DEV insertion policy.
    remaining = (
        0
        if runtime.turn_deadline is None
        else max(0, runtime.turn_deadline - runtime.clock())
    )
    deadline_ms = int(time.time() * 1000 + remaining * 1000)
    added.extend(
        (
            recovery_packet(
                fight, struct.pack(">i", fight.id), deadline_ms=deadline_ms
            ),
            action_transition(fight.id),
        )
    )
    return Transition(
        fight, runtime, tuple(packets) + tuple(runtime.prepare_delivery(added))
    )
