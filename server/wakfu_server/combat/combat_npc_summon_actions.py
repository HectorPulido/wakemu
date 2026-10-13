"""Actual registered monster-created summon books, separate from wild NPCs."""


def monster_creator_context(fight, actor, monsters):
    """Resolve a real caster chain to its existing encounter map authority."""
    if getattr(actor, "native_summon_source", None) is None:
        return None
    if fight.actors.get(actor.id) is not actor:
        raise ValueError("Summon caster is absent from the actual fight")
    current = actor
    seen = set()
    while getattr(current, "native_summon_source", None) is not None:
        if current.id in seen:
            raise ValueError("Cyclic native summon creator chain")
        seen.add(current.id)
        source = current.native_summon_source
        if (
            not isinstance(source, dict)
            or source.get("native_relation_source")
            != "big.new_bje.fdt_initial_registration"
        ):
            raise ValueError("Missing actual native summon creator source")
        identity = source.get("caster_id")
        if identity not in fight.actors:
            raise ValueError("Actual native summon creator is absent")
        current = fight.actors[identity]
    if current.controlled:
        return None
    descriptor = monsters.get(current.id)
    if (
        not isinstance(descriptor, dict)
        or descriptor.get("id") != current.id
        or type(descriptor.get("map_id")) is not int
    ):
        raise ValueError("Missing actual NPC creator encounter map authority")
    return dict(creator_id=current.id, map_id=descriptor["map_id"])


def registered_npc_summon_book(fight, actor, monsters):
    """Attest current QI registration, native control and exact fresh bPD book."""
    context = monster_creator_context(fight, actor, monsters)
    if context is None:
        raise ValueError("Actor is not an actual monster-created summon")
    from .combat_effective_control import effective_server_controlled

    if not effective_server_controlled(fight, actor):
        raise ValueError("Native monster summon is not currently server controlled")
    from .combat_summon_spellbook import actor_action_book
    from .combat_summon_stats import registered_summon_stats

    registered_summon_stats(actor, fight, context["map_id"])
    book = actor_action_book(actor)
    return context, {entry["reference"]: entry["level"] for entry in book["actions"]}


def registered_server_summon_book(
    fight, actor, monsters, *, character=None, player_characters=None
):
    """Use an actual registered AI summon, including a real player-owned root.

    A player-created child is never given a synthetic participant or class deck.
    Its native AI flag and fresh bPD book are independent of its root's input.
    """
    context = monster_creator_context(fight, actor, monsters)
    if context is None:
        current = actor
        seen = set()
        while getattr(current, "native_summon_source", None) is not None:
            if current.id in seen:
                raise ValueError("Cyclic native summon creator chain")
            seen.add(current.id)
            current = fight.actors[current.native_summon_source["caster_id"]]
        actual = (player_characters or {}).get(current.id)
        if (
            actual is None
            and isinstance(character, dict)
            and character.get("id") == current.id
        ):
            actual = character
        if (
            not current.controlled
            or not isinstance(actual, dict)
            or actual.get("id") != current.id
            or type(actual.get("map_id")) is not int
        ):
            raise ValueError("Missing actual player-root summon map authority")
        context = dict(creator_id=current.id, map_id=actual["map_id"])
    from .combat_effective_control import effective_server_controlled

    if not effective_server_controlled(fight, actor):
        raise ValueError("Registered summon is not currently native server controlled")
    from .combat_summon_spellbook import actor_action_book
    from .combat_summon_stats import registered_summon_stats

    registered_summon_stats(actor, fight, context["map_id"])
    book = actor_action_book(actor)
    return context, {entry["reference"]: entry["level"] for entry in book["actions"]}
