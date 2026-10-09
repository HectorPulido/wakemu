"""Prepare placement readiness and class initialization without partial commits."""
from copy import deepcopy
from .combat_runtime_messages import RuntimeMessages


def prepare_ready(
    fight,
    owner_id,
    ready,
    *,
    initialize,
    stats_serializer,
    effects_serializer,
    runtime_stats_serializer=None,
    turn_end_provider=None,
    turn_start_provider=None,
    expiration_runtime_factory=None,
    previous_native_action_id=0
):
    from .combat_native_action_ids import MAX_NATIVE_ACTION_ID

    if (
        type(previous_native_action_id) is not int
        or not 0 <= previous_native_action_id <= MAX_NATIVE_ACTION_ID
    ):
        raise ValueError("Invalid previous native action counter")
    if fight.phase == "active":
        if owner_id not in fight.ready_owners:
            raise ValueError("Readiness owner mismatch")
        return fight, None, ()
    preview = deepcopy(fight)
    preview.ready(owner_id, ready)
    if preview.phase != "active":
        return preview, None, ()
    # Capture the native baseline before innates modify characteristics. Empty
    # effect snapshots must precede initialization, otherwise they erase states.
    payloads = {
        actor.id: (stats_serializer(actor), effects_serializer())
        for actor in preview.actors.values()
    }
    preview, initialization = initialize(preview, 1)
    messages = RuntimeMessages(
        preview,
        stats_serializer=stats_serializer,
        runtime_stats_serializer=runtime_stats_serializer,
        turn_end_provider=turn_end_provider,
        turn_start_provider=turn_start_provider,
        expiration_runtime_factory=expiration_runtime_factory,
    )
    messages.action_id = 1  # reserve the transaction's native action identifier
    messages.native_action_id = previous_native_action_id
    packets = messages.combat_started(payloads, initialization_packets=initialization)
    return preview, messages, tuple(packets)
