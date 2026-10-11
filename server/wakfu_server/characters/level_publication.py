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
