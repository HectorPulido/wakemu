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
