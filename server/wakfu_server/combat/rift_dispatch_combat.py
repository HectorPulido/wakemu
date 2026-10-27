"""Accepted rift action preparation before checkpoint and public delivery."""
import struct

from wakfu_server.combat_shared import Transition


def finish_accepted_action(
    fight, runtime, packets, *, initialize_actor, initialize_wave=None
):
    """Consume a staged wave on a detached accepted preview, without DB writes.

    The caller synchronously checkpoints this result before returning it to the
    shared registry. Native sources live on the preview, never a mutable socket
    context shared with an operation that might still fail.
    """
    from wakfu_server.rift_dispatch_lifecycle import next_roster
    from wakfu_server.rift_npc_creation import install_native_wave

    state = getattr(fight, "rift_wave_state", None)
    if state is None:
        return Transition(fight, runtime, tuple(packets))
    pending = state.get("pending_wave")
    if fight.phase != "active" or pending is None:
        return Transition(fight, runtime, tuple(packets))
    if runtime is None or runtime.fight is not fight:
        raise ValueError("Rift accepted action has a stale native runtime")
    from wakfu_server.rift_policy import select_wave

    next_refs = select_wave(
        state["catalog"], state["policy"], state["seed"], pending["completed_wave"] + 1
    )
    from wakfu_server.combat_snapshot_actor_visibility import hidden_snapshot_actor_ids

    visible_count = len(fight.actors) - len(hidden_snapshot_actor_ids(fight))
    if visible_count + len(next_refs) > 127:
        # Native signed-byte presentation limits apply to current participants,
        # not irreversible historical actors retained for sources and rewards.
        # Concurrent capacity is not an official win or reward entitlement.
        fight.phase = "finished"
        from wakfu_server.combat_encounter_roles import assigned_roles

        fight.winner = assigned_roles(fight).npc_team
        state["outcome"] = "capacity_exhausted"
        state["last_cleared_wave"] = dict(pending)
        state["pending_wave"] = None
        fight._event(
            "finished", winner=fight.winner, reason="rift_native_history_capacity"
        )
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
    added = install_native_wave(
        fight,
        monsters,
        initialize_actor=initialize_actor,
        initialize_wave=initialize_wave,
    )
    from wakfu_server.combat_native_action_ids import NATIVE_ACTION_PACKETS

    if 13051 in NATIVE_ACTION_PACKETS:
        added.append(
            (
                13051,
                struct.pack(">iiii", fight.id, runtime.action_id, -1, state["wave"]),
            )
        )
    from wakfu_server.rift_publication_fence import publish_births_before_ack

    published = publish_births_before_ack(
        runtime,
        packets,
        added,
        actor_ids=state["wave_actor_ids"],
    )
    return Transition(fight, runtime, published)
