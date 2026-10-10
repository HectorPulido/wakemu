"""Connected player inputs for shared casts, including owned summons."""


def connected_cast_source(characters, decks, character_id, account_id):
    """Select the connected owner; actor authorization happens in cast resolution.

    A summon never becomes a player source and never receives this deck as its
    action book. resolve_owned_spell_action validates its own registered book.
    """
    source = characters.get(character_id)
    if (
        not isinstance(source, dict)
        or source.get("id") != character_id
        or source.get("account_id") != account_id
        or character_id not in decks
    ):
        raise ValueError("Connected caster owner has no current player snapshot/deck")
    return source, decks[character_id]


def connected_action_source(
    fight, characters, decks, main_character_id, account_id, actor_id
):
    """Select a hero's own build, or its verified summoner's build context."""
    connected_cast_source(characters, decks, main_character_id, account_id)
    actor = fight.actors.get(actor_id)
    if actor is None or not actor.controlled or actor.owner_id != account_id:
        raise ValueError("Action actor is not controlled by the connected account")
    identity, seen = actor_id, set()
    registrations = getattr(fight, "native_summon_registrations", {})
    while identity not in characters:
        if identity in seen:
            raise ValueError("Cyclic native summon owner chain")
        seen.add(identity)
        registration = registrations.get(identity)
        if (
            not isinstance(registration, dict)
            or registration.get("actor_id") != identity
        ):
            raise ValueError("Action actor lacks a verified player owner")
        identity = registration.get("caster_id")
        caster = fight.actors.get(identity)
        if caster is None or not caster.controlled or caster.owner_id != account_id:
            raise ValueError("Native summon belongs to another account")
    return connected_cast_source(characters, decks, identity, account_id)
