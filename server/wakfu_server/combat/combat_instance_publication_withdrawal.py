"""Retire only an authorized withdrawn owner's ephemeral publication lease."""
from .combat_instance_publication import (
    PartyPublicationLease,
    native_roster_bindings,
    require_current_publication,
)


def retire_withdrawn_publication(fight, owner_id):
    """Run on the private withdrawal candidate, before its durable adoption.

    Historical actors and their original difficulty snapshots stay intact.
    Transport loss alone cannot qualify an owner for this operation.
    """
    if not getattr(fight, "native_instance_publication_required", False):
        return False
    lease = getattr(fight, "native_instance_publication_lease", None)
    receipt = getattr(fight, "native_instance_publication_receipt", None)
    if (
        lease is None
        and receipt is None
        and not getattr(fight, "native_instance_difficulty_snapshots", None)
    ):
        return False
    require_current_publication(fight)
    players, _npcs = native_roster_bindings(fight)
    owned = tuple(
        identity for identity in players if fight.actors[identity].owner_id == owner_id
    )
    if not owned or any(
        not getattr(fight.actors[identity], "pve_withdrawn", False)
        for identity in owned
    ):
        raise ValueError(
            "Publication retirement requires the complete withdrawn owner roster"
        )
    bindings = getattr(lease, "owner_bindings", ())
    receipts = receipt if isinstance(lease, PartyPublicationLease) else (receipt,)
    if not bindings or len(bindings) != len(receipts):
        raise ValueError("Publication retirement lacks original owner authority")
    if sum(scope[0] == owner_id for _source, scope in bindings) != 1:
        raise ValueError("Publication retirement owner is absent or duplicated")
    remaining = tuple(
        (binding, value)
        for binding, value in zip(bindings, receipts)
        if binding[1][0] != owner_id
    )
    if not remaining:
        raise ValueError("Last published owner requires full combat abandonment")
    sources = tuple(binding for binding, _value in remaining)
    expected = tuple(value for _binding, value in remaining)
    replacement = PartyPublicationLease(
        tuple(source.lease for source, _scope in sources),
        sources,
    )
    if replacement.current != expected:
        raise ValueError("Remaining owner publication changed during withdrawal")
    fight.native_instance_publication_lease = replacement
    fight.native_instance_publication_receipt = expected
    return True
