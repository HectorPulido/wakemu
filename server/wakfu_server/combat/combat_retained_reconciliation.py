"""Reconcile registered UIDs from native membership deltas.

Container snapshots and retired area roots remain the runtime's separate cleanup
phase. This helper does not certify those mutable payloads.
"""
from .combat_state_membership import membership_live


def reconcile_registered_uids(owner, pending):
    """Return False before mutation if stored order needs legacy reconciliation."""
    owner._refresh_order()
    if not owner.valid or owner.order_mismatch:
        return False
    ledgers = membership_live(owner)
    if ledgers is None:
        return False
    # Metadata can only become absent from the union through a source removal.
    # Ledger-only entries remain live, and scoped pending UIDs are excluded by
    # the legacy _live contract even when metadata was incorrectly published.
    removed = tuple(
        uid
        for uid in owner.unmatched | pending
        if uid in owner.records
        and (uid in pending or (uid not in owner.source_counts and uid not in ledgers))
    )
    for uid in removed:
        del owner.records[uid]
    if removed:
        removed = frozenset(removed)
        owner.order[:] = [uid for uid in owner.order if uid not in removed]
    return True
