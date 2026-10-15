"""Prepare every cast presentation packet before committing its preview.

Call on the owning session thread. No network sends occur here; caller sends
returned packets and handles death/results after accepting the new fight.
"""
import struct
import time
from .combat_spell_transaction import SpellTransaction
from .combat_wire import actor_state
from .combat_geometry_snapshot import source_snapshot


def commit_spell_transaction(
    runtime, transaction, *, stats_serializer, diagnostic=None
):
    def stage(name, started, **details):
        if diagnostic is not None:
            diagnostic(
                phase=name,
                elapsed_ms=round((time.monotonic() - started) * 1000, 3),
                fight_id=runtime.fight.id,
                action_id=transaction.action_id,
                **details
            )

    if not isinstance(transaction, SpellTransaction) or not callable(stats_serializer):
        raise ValueError("Missing prepared spell transaction or serializer")
    if runtime.awaiting_ack is not None or runtime.pending:
        raise ValueError("Previous combat action is not synchronized")
    if transaction.action_id != runtime.action_id + 1:
        raise ValueError("Prepared spell action sequence is stale")
    started = time.monotonic()
    if (
        transaction.fight.id != runtime.fight.id
        or source_snapshot(runtime.fight) != transaction.source_state
    ):
        raise ValueError("Combat changed after preparing the spell")
    stage("validate_source", started)
    expected = struct.pack(">iii", runtime.fight.id, transaction.action_id, -1)
    for opcode, payload in transaction.packets:
        if not isinstance(payload, bytes) or payload[:12] != expected:
            raise ValueError("Effect packet belongs to another combat action")
    packets = list(transaction.packets)
    packets.append(runtime._flush())
    from .combat_snapshot_actor_visibility import hidden_snapshot_actor_ids

    hidden = hidden_snapshot_actor_ids(transaction.fight)
    for actor in transaction.fight.actors.values():
        # Native final-death delivery still needs the client's registered QK
        # byte. Publishing an already retired obstacle=-1 first prevents
        # QI.g(QK) from clearing its former slot and occupied cells.
        if actor.id in hidden:
            continue
        started = time.monotonic()
        stats = stats_serializer(actor, transaction.fight)
        stage("serialize_actor", started, actor_id=actor.id)
        packets.append(
            (12873, actor_state(12873, transaction.fight.id, actor.id, stats))
        )
    packets.append(runtime._flush())
    # Serialization callbacks cannot invalidate the original source silently.
    started = time.monotonic()
    if source_snapshot(runtime.fight) != transaction.source_state:
        raise ValueError("Combat changed while serializing the spell")
    stage("revalidate_source", started)
    delivery = runtime.prepare_delivery(packets)
    runtime.fight = transaction.fight
    runtime.action_id = transaction.action_id
    return delivery
