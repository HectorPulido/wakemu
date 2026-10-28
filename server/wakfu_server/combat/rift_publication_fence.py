"""Native ordinary births precede the real end-turn presentation ACK.

13091 queues aVH and inserts the actor through cYp. Recovery12053 instead
destroys that queue manager and restores SU immediately. A later real
12502/aUM ->13510 is the existing proof that earlier queued births finished;
neither13051 nor13420 acknowledges their completion.
"""
import struct
import time


def birth_fence(fight):
    receipt = getattr(fight, "native_rift_birth_fence", None)
    if receipt is None:
        return None
    if (
        not isinstance(receipt, dict)
        or receipt.get("policy") != "wakemu.ordinary-birth-real-turn-ack-v1"
        or type(receipt.get("ack_turn")) is not int
        or receipt["ack_turn"] < 1
        or not isinstance(receipt.get("actor_ids"), list)
        or not receipt["actor_ids"]
        or len(set(receipt["actor_ids"])) != len(receipt["actor_ids"])
        or any(identity not in fight.actors for identity in receipt["actor_ids"])
    ):
        raise ValueError("Invalid pending native ordinary birth fence")
    return receipt


def _refresh_pending_timeline(runtime):
    """Replace presentation only; never rerun already committed start effects."""
    from wakfu_server.combat_recovery import recovery_packet
    from wakfu_server.combat_turn_duration import current_turn_duration
    from wakfu_server.combat_wire import actor_state

    fight = runtime.fight
    actor = fight.current
    if runtime.awaiting_ack is None or actor is None or fight.phase != "active":
        raise ValueError("Birth timeline refresh requires the actual pending turn ACK")
    # Callback effects, births, removals and other actors' stat updates remain
    # in their original order. Only the obsolete turn/SU frames are replaced.
    frames = {12053, 13337, 13482, 13477}
    pending = [
        (opcode, payload) for opcode, payload in runtime.pending if opcode not in frames
    ]
    duration = current_turn_duration(fight, runtime.duration)
    pending.append(
        recovery_packet(
            fight,
            struct.pack(">i", fight.id),
            deadline_ms=int(time.time() * 1000) + duration,
            new_turn=True,
        )
    )
    serialize = runtime.runtime_stats_serializer
    if serialize is not None or runtime.stats_serializer is not None:
        stats = (
            serialize(actor, fight)
            if serialize is not None
            else runtime.stats_serializer(actor)
        )
        pending.append((12873, actor_state(12873, fight.id, actor.id, stats)))
    pending.extend(
        (
            runtime._flush(),
            (13337, runtime._prefix() + struct.pack(">qq", actor.id, duration)),
            runtime._flush(),
            (13482, runtime._prefix() + struct.pack(">qq", actor.id, duration)),
            runtime._flush(),
        )
    )
    runtime.pending = pending
    runtime.native_initial_timeline_restore_pending = False
    runtime.native_timeline_restore_pending_turn = fight.turn_id


def publish_births_before_ack(runtime, packets, added, *, actor_ids):
    """Stage births now and the destructive full timeline behind a real ACK."""
    fight = runtime.fight
    if fight.phase != "active" or fight.current is None or not actor_ids:
        raise ValueError("Ordinary birth publication requires its active native fight")
    packets = tuple(packets)
    ending = next(
        (index for index, (opcode, _) in enumerate(packets) if opcode == 12502), None
    )
    if runtime.awaiting_ack is not None and ending is None:
        raise ValueError(
            "Ordinary births cannot cross an already published end-turn ACK"
        )
    counter = fight.turn_id if runtime.awaiting_ack is None else runtime.awaiting_ack
    previous = birth_fence(fight)
    if previous is not None and previous["ack_turn"] != counter:
        raise ValueError("Ordinary births crossed another native turn fence")
    identities = [] if previous is None else list(previous["actor_ids"])
    if set(identities) & set(actor_ids) or any(
        identity not in fight.actors for identity in actor_ids
    ):
        raise ValueError("Ordinary birth publication reused a native actor")
    fight.native_rift_birth_fence = dict(
        policy="wakemu.ordinary-birth-real-turn-ack-v1",
        ack_turn=counter,
        actor_ids=identities + list(actor_ids),
    )
    if runtime.awaiting_ack is None:
        # A spell never ends its owner just to synchronize presentation. The
        # ordinary subsequent end builds the replacement behind its real ACK.
        runtime.native_initial_timeline_restore_pending = True
    else:
        _refresh_pending_timeline(runtime)
    prepared = tuple(runtime.prepare_delivery((*added, runtime._flush())))
    if ending is None:
        return packets + prepared
    # aUM must be queued AFTER aVH. Merely sending birth packets before the
    # pending recovery but after12502 would allow a premature13510.
    return packets[:ending] + prepared + packets[ending:]


def release_birth_fence(runtime, counter):
    receipt = birth_fence(runtime.fight)
    if receipt is None:
        return
    if receipt["ack_turn"] != counter:
        raise ValueError("Native turn ACK does not complete its ordinary births")
    runtime.fight.native_rift_birth_fence = None
