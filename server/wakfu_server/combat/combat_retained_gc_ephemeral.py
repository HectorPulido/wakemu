"""Recognize the omitted live providers before terminal effect collection."""


def _receipt(value):
    kind = type(value)
    if value is None or kind is int or kind is str or kind is bool:
        return True
    return kind is tuple and all(_receipt(item) for item in value)


def _publication_source_known(lease):
    from .combat_instance_publication import (
        PublicationLease,
        PartyPublicationLease,
        InstancePublicationTracker,
    )

    kind = type(lease)
    if kind is not PublicationLease and kind is not PartyPublicationLease:
        return False
    fields = vars(lease)
    if kind is PublicationLease:
        if not _receipt(fields.get("current")):
            return False
    else:
        children = fields.get("leases")
        if type(children) is not tuple or any(
            type(child) is not PublicationLease
            or not _receipt(vars(child).get("current"))
            for child in children
        ):
            return False
    bindings = fields.get("owner_bindings", ())
    if type(bindings) is not tuple:
        return False
    for binding in bindings:
        if type(binding) is not tuple or len(binding) != 2:
            return False
        tracker, scope = binding
        if type(tracker) is not InstancePublicationTracker or not _receipt(scope):
            return False
        source = vars(tracker)
        child = source.get("lease")
        if (
            type(child) is not PublicationLease
            or not _receipt(vars(child).get("current"))
            or not _receipt(source.get("scope"))
        ):
            return False
    return True


def ephemeral_sources_known(fight):
    """Opaque callbacks abstain; recognized providers still read fresh state.

    Actor data is checked separately by the boundary. No provider is invoked,
    frozen, or traversed through character inventories here.
    """
    fields = vars(fight)
    provider = fields.get("native_rail_movement_authority")
    if provider is not None:
        from .combat_summon import RegisteredSummonAuthority
        from .combat_ordinary_authority import (
            OrdinaryActorAuthority,
            _immutable_property_catalog,
        )
        from .combat_npc_spellbook import ordinary_npc_spellbook

        if type(provider) is not RegisteredSummonAuthority:
            return False
        ordinary = vars(provider).get("ordinary")
        if type(ordinary) is not OrdinaryActorAuthority:
            return False
        source = vars(ordinary)
        spellbook = source.get("npc_spellbook")
        if source.get("catalog") is not _immutable_property_catalog() or (
            spellbook is not None and spellbook is not ordinary_npc_spellbook
        ):
            return False
    lease = fields.get("native_instance_publication_lease")
    if lease is not None and not _publication_source_known(lease):
        return False
    committed = fields.get("native_consumable_handoff_committed", frozenset())
    return type(committed) is frozenset and all(type(uid) is int for uid in committed)
