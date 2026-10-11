"""Publish an authoritative dungeon or restored owned build through native codecs."""
from protocol_codec import Reader
from wakfu_server import builds, wire
from wakfu_server.characters import hero_wire


def owned_hero_role(db, account_id, character_id):
    """Classify only from the durable native company roster, including switches."""
    roster = db.execute(
        "SELECT leader_id FROM account_hero_rosters WHERE account_id=%s", (account_id,)
    ).fetchone()
    if roster is None or roster["leader_id"] == character_id:
        return False
    member = db.execute(
        "SELECT 1 FROM account_hero_slots WHERE account_id=%s AND character_id=%s",
        (account_id, character_id),
    ).fetchone()
    if member is None:
        raise ValueError("Published character is not in the authoritative company")
    return True


def packets(character, fixture_provider, *, owned_characters=None, owned_hero=False):
    """Encode everything before delivery; never derive a second modulation profile.

    Store.character must be freshly loaded after boundary health reconciliation.
    The same path publishes a temporary dungeon build or the restored owned build.
    """
    if not callable(fixture_provider):
        raise ValueError("Native build publication requires original fixtures")
    if character.get("level") is None:
        raise ValueError("Native build publication requires an owned character")
    # Validate the selected index against the complete fresh build registry first.
    selection = builds.selection_message(character)
    original_owned = fixture_provider(12666)
    reader = Reader(original_owned)
    reader.take(reader.number("H") * 8)
    template = reader.take(reader.number("I"))
    if not template or template[0] != 10:
        raise ValueError("Native owned build publication requires format10")
    roster = tuple(owned_characters) if owned_characters is not None else (character,)
    if not roster or not any(row["id"] == character["id"] for row in roster):
        raise ValueError("Native equipment registry omits the published character")
    if any(row["account_id"] != character["account_id"] for row in roster):
        raise ValueError("Native build publication includes a foreign account")
    registry = (
        hero_wire.activate(template, character)
        if owned_hero
        else (
            12666,
            wire.adapt(12666, original_owned, character["account_id"], character),
        )
    )
    equipment = (12393, wire.attribute_sheets(fixture_provider(12393), roster))
    appearance = hero_wire.refresh(template, character)
    from wakfu_server.combat_lifecycle import outside_progression

    progression = outside_progression(character)
    return (registry, equipment, selection, appearance, progression)
