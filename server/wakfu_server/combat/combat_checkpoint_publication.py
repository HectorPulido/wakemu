"""Receipt for a final private Rift state persisted before its publication."""
from dataclasses import dataclass


@dataclass(frozen=True)
class CheckpointPublication:
    fight: object
    runtime: object
    revision: int
    sequence: int


def persist_prepared(shared, fight, runtime, packets):
    """Persist after all gameplay/presentation preparation, before adoption."""
    from .combat_turn_receipt_history import prune_published_turn_receipts

    prune_published_turn_receipts(fight, runtime, packets)
    if getattr(fight, "rift_wave_state", None) is None:
        return
    context = shared.join_context
    writer = (
        context.get("rift_checkpoint_action") if isinstance(context, dict) else None
    )
    if writer is None:
        return  # Older/custom providers may own their checkpoint boundary.
    if not callable(writer):
        raise ValueError("Rift final checkpoint provider is invalid")
    writer(shared, fight, runtime, packets)
    revision = shared.checkpoint_revision
    if type(revision) is not int or revision < 1:
        raise ValueError("Rift final checkpoint did not publish its revision")
    shared.checkpoint_publication = CheckpointPublication(
        fight, runtime, revision, shared.sequence + 1
    )


def is_checkpointed_publication(shared):
    """Only for callers immediately following a successful Registry operation.

    This is publication provenance, not a generic mutable-state change detector.
    Direct mutations, logout and terminal saves must use the normal writer.
    """
    receipt = getattr(shared, "checkpoint_publication", None)
    return (
        isinstance(receipt, CheckpointPublication)
        and receipt.fight is shared.fight
        and receipt.runtime is shared.runtime
        and receipt.revision == shared.checkpoint_revision
        and receipt.sequence == shared.sequence
    )
