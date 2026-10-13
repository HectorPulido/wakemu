"""Materialize virtual starter loadouts once during authorized selection."""
from wakfu_server import builds
from wakfu_server.spells import default_deck
from wakfu_server.wire import proto_fields


def initialize(db, character):
    """Caller holds account/session/character locks; retain all saved metadata."""
    saved = character.get("builds", {})
    if 0 not in saved:
        sheet = next(
            value
            for tag, value in proto_fields(builds.build_set(character, b""))
            if tag == 18
        )
        db.execute(
            "INSERT INTO character_builds(character_id,build_index,sheet,equipment,deck,aptitudes) "
            "VALUES(%s,0,%s,%s,%s,%s) ON CONFLICT(character_id,build_index) DO NOTHING",
            (
                character["id"],
                sheet,
                b"",
                default_deck(dict(character, effective_level=character["level"])),
                b"",
            ),
        )
    for index, record in saved.items():
        if not record.get("deck"):
            level = builds.effective_sheet_level(character, index)
            db.execute(
                "UPDATE character_builds SET deck=%s WHERE character_id=%s AND build_index=%s "
                "AND octet_length(deck)=0",
                (
                    default_deck(dict(character, effective_level=level)),
                    character["id"],
                    index,
                ),
            )
