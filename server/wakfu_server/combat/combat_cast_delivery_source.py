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
    if actor is None:
        raise ValueError("Action actor is not controlled by the connected account")
    controller_book = getattr(fight, "native_controller_action_books", {}).get(actor_id)
    if (
        not actor.controlled
        or actor.owner_id != account_id
        or controller_book is not None
    ):
        from .combat_effective_control import require_effective_owner
        from .combat_controller_registry import current_native_controller

        require_effective_owner(fight, actor, account_id)
        controller_id = current_native_controller(fight, actor_id)
        controller = fight.actors.get(controller_id)
        if (
            controller is None
            or not controller.controlled
            or controller.owner_id != account_id
        ):
            raise ValueError("Action actor lacks its actual current human controller")
        if controller_book is not None:
            if (
                not isinstance(controller_book, dict)
                or controller_book.get("producer") != "eWD207.eZd.fQM.actual"
                or controller_book.get("controller_id") != controller_id
                or type(controller_book.get("running_uid")) is not int
                or not isinstance(controller_book.get("actions"), tuple)
            ):
                raise ValueError(
                    "Action actor lacks its actual published controller book"
                )
        else:
            from .combat_encounter_scene_helpers import controlled_scene_helper

            if not controlled_scene_helper(
                fight, actor, character_id=controller_id, account_id=account_id
            ):
                raise ValueError(
                    "Action NPC lacks a source-qualified current controller"
                )
        return connected_cast_source(characters, decks, controller_id, account_id)
    from .combat_companions import registered_source

    companion = getattr(fight, "native_companion_sources", {}).get(str(actor_id))
    if companion is not None:
        registered_source(fight, actor, companion)
        return connected_cast_source(
            characters, decks, companion["owner_character_id"], account_id
        )
    identity, seen = actor_id, set()
    registrations = getattr(fight, "native_summon_registrations", {})
    while identity not in characters:
        if identity in seen:
            raise ValueError("Cyclic native summon owner chain")
        seen.add(identity)
        companion = getattr(fight, "native_companion_sources", {}).get(str(identity))
        if companion is not None:
            registered_source(fight, fight.actors[identity], companion)
            if companion["account_id"] != account_id:
                raise ValueError("Companion controller belongs to another account")
            identity = companion["owner_character_id"]
            continue
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
