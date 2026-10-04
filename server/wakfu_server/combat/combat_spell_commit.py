"""Prepare every cast presentation packet before committing its preview.

Call on the owning session thread. No network sends occur here; caller sends
returned packets and handles death/results after accepting the new fight.
"""
import struct
from .combat_spell_transaction import SpellTransaction
from .combat_wire import actor_state
from .fight_checkpoint_store import snapshot


def commit_spell_transaction(runtime, transaction, *, stats_serializer):
    if not isinstance(transaction, SpellTransaction) or not callable(stats_serializer):
        raise ValueError("Missing prepared spell transaction or serializer")
    if runtime.awaiting_ack is not None or runtime.pending:
        raise ValueError("Previous combat action is not synchronized")
    if transaction.action_id != runtime.action_id + 1:
        raise ValueError("Prepared spell action sequence is stale")
    if (
        transaction.fight.id != runtime.fight.id
        or snapshot(runtime.fight) != transaction.source_state
    ):
        raise ValueError("Combat changed after preparing the spell")
    expected = struct.pack(">iii", runtime.fight.id, transaction.action_id, -1)
    for opcode, payload in transaction.packets:
        if not isinstance(payload, bytes) or payload[:12] != expected:
            raise ValueError("Effect packet belongs to another combat action")
    packets = list(transaction.packets)
    packets.append(runtime._flush())
    for actor in transaction.fight.actors.values():
        stats = stats_serializer(actor, transaction.fight)
        packets.append(
            (12873, actor_state(12873, transaction.fight.id, actor.id, stats))
        )
    packets.append(runtime._flush())
    # Serialization callbacks cannot invalidate the original source silently.
    if snapshot(runtime.fight) != transaction.source_state:
        raise ValueError("Combat changed while serializing the spell")
    runtime.fight = transaction.fight
    runtime.action_id = transaction.action_id
    return tuple(packets)
