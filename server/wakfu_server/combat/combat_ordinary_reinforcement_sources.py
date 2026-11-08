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


def current_monster_source(fight, captured, actor_id, *, map_id=None):
    """Read one actual source and its own birth receipt, not the historical roster."""
    state = getattr(fight, "rift_wave_state", None)
    if state is None:
        return captured.get(actor_id)
    from .combat_state import Fight, Actor
    from .combat_retained_collections import OwnedMap

    actors = getattr(fight, "actors", None)
    if (
        type(fight) is not Fight
        or Fight.__getattribute__ is not object.__getattribute__
        or type(captured) is not dict
        or type(actor_id) is not int
        or type(state) is not dict
        or (type(actors) is not dict and type(actors) is not OwnedMap)
    ):
        return current_monster_sources(fight, captured, map_id=map_id).get(actor_id)
    actor = dict.get(actors, actor_id)
    sources = getattr(fight, "rift_monsters", None)
    if type(actor) is not Actor or type(sources) is not dict:
        return current_monster_sources(fight, captured, map_id=map_id).get(actor_id)
    source = captured.get(actor_id)
    if source is not None:
        if sources.get(actor_id) != source:
            raise ValueError(
                "Ordinary reinforcement sources changed captured authority"
            )
        return source
    locations = getattr(fight, "native_rift_birth_locations", None)
    if type(locations) is not dict or actor_id not in locations:
        # Old stored fights without the producer locator retain their complete
        # birth verification. Every fresh native acknowledge_wave emits it.
        return current_monster_sources(fight, captured, map_id=map_id).get(actor_id)
    location = locations[actor_id]
    receipts = state.get("staged_receipts")
    if (
        type(location) is not tuple
        or len(location) != 2
        or any(type(value) is not int or value < 0 for value in location)
        or type(receipts) is not list
        or location[0] >= len(receipts)
    ):
        raise ValueError("Invalid ordinary reinforcement source location")
    receipt = receipts[location[0]]
    identities = receipt.get("next_actor_ids") if type(receipt) is dict else None
    references = receipt.get("next_species_refs") if type(receipt) is dict else None
    offset = location[1]
    if (
        type(identities) is not list
        or type(references) is not list
        or len(identities) != len(references)
        or offset >= len(identities)
        or identities[offset] != actor_id
        or identities.count(actor_id) != 1
        or type(references[offset]) is not int
        or references[offset] <= 0
    ):
        raise ValueError("Invalid ordinary reinforcement source receipt")
    from .rift_combat_adapter import creation_delivery
    from .combat_encounter_roles import assigned_roles

    creation_delivery(fight, actor_id)
    source = sources.get(actor_id)
    if (
        actor_id >= 0
        or actor.controlled
        or actor_id in getattr(fight, "native_summon_registrations", {})
        or type(source) is not dict
        or source.get("id") != actor_id
        or source.get("ref") != references[offset]
        or source.get("level") != actor.effective_level
        or source.get("instance_id") != state.get("instance_id")
        or (map_id is not None and source.get("map_id") != map_id)
        or actor.team != assigned_roles(fight).npc_team
        or actor.native_obstacle_id is None
    ):
        raise ValueError("Ordinary reinforcement lacks its native owned source")
    return source
