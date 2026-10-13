"""Refresh existing owned spellbooks and roster levels after progression."""
from wakfu_server import wire


def refresh(character, characters, *, entity_template, roster_template):
    """Publish updates without activating another actor or resetting the map.

    Format3 progression updates HP/XP, but does not contain the spell inventory.
    The verified owned format10 supplies that missing component through15548.
    The roster update supplies the real level used by native build availability.
    """
    if not entity_template or entity_template[0] != 10:
        raise ValueError("Level publication requires the owned format10 template")
    layout = wire.ENTITY_LAYOUTS.get(10, {})
    names = {section["name"] for section in layout.get("sections", ())}
    if not {"SPELL_INVENTORY", "SPELL_DECK"} <= names:
        raise ValueError("Owned level refresh is missing spell components")
    roster = list(characters)
    matches = [entry for entry in roster if entry["id"] == character["id"]]
    if len(matches) != 1 or matches[0]["level"] != character["level"]:
        raise ValueError("Level publication requires the current owned roster")
    if any(entry["account_id"] != character["account_id"] for entry in roster):
        raise ValueError("Level publication cannot include foreign characters")
    return [
        wire.refresh_player(entity_template, character),
        (
            23548,
            wire.character_list(roster_template, character["account_id"], roster),
        ),
    ]


def combat_return(
    character, characters, *, participant_ids, entity_template, roster_template
):
    """Refresh the selected actor and loaded owned heroes after world restore."""
    from wakfu_server.characters import hero_wire

    roster = list(characters)
    packets = refresh(
        character,
        roster,
        entity_template=entity_template,
        roster_template=roster_template,
    )
    participants = set(participant_ids)
    for hero in roster:
        if hero["id"] != character["id"] and hero["id"] in participants:
            # Private scene positions are projections, not durable exterior rows.
            if "map_id" in character and (
                hero.get("map_id"),
                hero.get("instance_id", 0),
            ) != (character["map_id"], character.get("instance_id", 0)):
                hero = dict(
                    hero,
                    **{
                        key: character[key]
                        for key in ("map_id", "instance_id", "x", "y", "z")
                    }
                )
            # csZ updates an existing hero; it never activates it as main.
            packets.extend(
                (hero_wire.refresh(entity_template, hero), hero_wire.statistics(hero))
            )
    return packets
