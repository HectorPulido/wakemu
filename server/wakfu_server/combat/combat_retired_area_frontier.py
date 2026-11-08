"""Operation-local retired-area reachability over certified indexed facts.

This helper does not establish authority or observe mutations. Its caller must
own complete area/source indexes and fall back when any producer is opaque.
"""


def retired_area_frontier(*, owners, inbound, roots, active, protected, dirty):
    """Return (prunable, examined) without changing the supplied indexes.

    owners contains every active and retired area, mapping to its owner_id.
    inbound maps owner identities to area identities pointing to that owner.
    roots maps external source identities to their positive reference counts.
    active areas and protected retired callback/ledger holders are roots too.

    Walk only affected weak components, then trace actual directed ownership
    from their external roots. Reference counts alone cannot release cycles.
    The caller includes old/new endpoints when an edge changes and surviving
    neighbors when deleting a node. Initial admission marks every node dirty.
    """
    examined = set()
    pending = [identity for identity in dirty if identity in owners]
    while pending:
        identity = pending.pop()
        if identity in examined:
            continue
        examined.add(identity)
        owner = owners[identity]
        if owner in owners and owner not in examined:
            pending.append(owner)
        pending.extend(
            child
            for child in inbound.get(identity, ())
            if child in owners and child not in examined
        )
    reachable = set()
    pending = [
        identity
        for identity in examined
        if identity in active or identity in protected or roots.get(identity, 0)
    ]
    while pending:
        identity = pending.pop()
        if identity in reachable:
            continue
        reachable.add(identity)
        owner = owners[identity]
        if owner in examined and owner not in reachable:
            pending.append(owner)
    return frozenset(examined - reachable), frozenset(examined)
