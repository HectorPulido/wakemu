"""Ordered state membership mutations shared by native state consumers.

Native definitions, application planning and callback execution remain at their
existing owners. These operations publish against the current ledger after
callbacks, preserving recursive removals and exact object/UID distinctions.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class StateMembershipChange:
    remove_uids: frozenset
    append: tuple = ()


def publish_membership(ledger, change):
    """Retire exact carrier UIDs and append retained carriers in native order."""
    retained = tuple(
        item for item in ledger._entries if item.uid not in change.remove_uids
    )
    ledger._entries = retained + change.append


def publish_application(ledger, applied, removed):
    # Read membership after before_replace callbacks, not from a stale plan.
    publish_membership(
        ledger,
        StateMembershipChange(
            frozenset(item.uid for item in removed),
            (applied,) if applied.retained else (),
        ),
    )


def remove_carrier(ledger, uid):
    removed = next((item for item in ledger._entries if item.uid == uid), None)
    if removed is not None:
        publish_membership(ledger, StateMembershipChange(frozenset((uid,))))
    return removed


def replace_carrier(ledger, original, updated, *, by_identity):
    """Timer publication preserves the caller's identity-versus-UID contract."""
    if by_identity:
        ledger._entries = tuple(
            updated if item is original else item for item in ledger._entries
        )
    else:
        ledger._entries = tuple(
            updated if item.uid == original.uid else item for item in ledger._entries
        )


def expire_carriers(ledger, *, actor_id, round_number, phase, round_cleanup):
    removed = []
    for item in ledger._entries:
        if item.timer is None:
            continue
        expired = (
            item.timer.expires_at_round_cleanup(round_number)
            if round_cleanup
            else item.timer.expires_on(
                actor_id=actor_id,
                round_number=round_number,
                phase=phase,
            )
        )
        if expired:
            removed.append(item)
    removed = tuple(removed)
    publish_membership(
        ledger, StateMembershipChange(frozenset(item.uid for item in removed))
    )
    return removed
