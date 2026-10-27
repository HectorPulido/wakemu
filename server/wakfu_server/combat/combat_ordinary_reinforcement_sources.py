"""Refresh captured ordinary sources only from committed native wave births."""


def current_monster_sources(fight, captured, *, map_id=None):
    """Preserve old descriptors and admit exact registered reinforcement IDs.

    Native AI lifecycle callbacks can outlive the roster with which they were
    constructed. The fight owns later ordinary births; actor statistics alone
    are never a substitute for their original species and instance source.
    """
    state = getattr(fight, "rift_wave_state", None)
    if state is None:
        return captured
    registrations = getattr(fight, "native_summon_registrations", {})
    ordinary = {
        identity
        for identity, actor in fight.actors.items()
        if not actor.controlled and identity not in registrations
    }
    missing = ordinary - set(captured)
    if not missing:
        return captured
    sources = getattr(fight, "rift_monsters", None)
    if (
        not isinstance(state, dict)
        or not isinstance(sources, dict)
        or set(sources) != ordinary
        or any(
            identity not in sources or sources[identity] != source
            for identity, source in captured.items()
        )
    ):
        raise ValueError("Ordinary reinforcement sources changed captured authority")
    receipts = state.get("staged_receipts")
    if not isinstance(receipts, list):
        raise ValueError("Ordinary reinforcement lacks committed wave receipts")
    species = {}
    for receipt in receipts:
        identities, references = receipt.get("next_actor_ids"), receipt.get(
            "next_species_refs"
        )
        if (
            not isinstance(identities, list)
            or not isinstance(references, list)
            or len(identities) != len(references)
            or len(set(identities)) != len(identities)
        ):
            raise ValueError("Invalid ordinary reinforcement source receipt")
        for identity, reference in zip(identities, references):
            if identity in species or type(reference) is not int or reference <= 0:
                raise ValueError("Ordinary reinforcement identity was reused")
            species[identity] = reference
    from .rift_combat_adapter import creation_replay

    # Existing decoder verifies the exact world/admission opcode, actor and
    # fight identities. It only reads the unpublished/committed birth ledger.
    creation_replay(fight)
    from wakfu_server.combat_encounter_roles import assigned_roles

    npc_team = assigned_roles(fight).npc_team
    deliveries = getattr(fight, "native_rift_creation_deliveries", {})
    for identity in missing:
        actor, source = fight.actors[identity], sources[identity]
        if (
            type(identity) is not int
            or identity >= 0
            or identity not in species
            or identity not in deliveries
            or not isinstance(source, dict)
            or source.get("id") != identity
            or source.get("ref") != species[identity]
            or source.get("level") != actor.effective_level
            or source.get("instance_id") != state.get("instance_id")
            or (map_id is not None and source.get("map_id") != map_id)
            or actor.team != npc_team
            or actor.native_obstacle_id is None
        ):
            raise ValueError("Ordinary reinforcement lacks its native owned source")
    return sources
