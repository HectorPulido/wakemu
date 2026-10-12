"""Validate roots from the same native table used by actual spell transactions."""


def native_scene_casting_row(spell, spell_level, casting, *, zero_casting=None):
    from wakfu_server.combat_native_spell_casting import native_casting_table

    record, index = native_casting_table(
        spell, spell_level, casting=casting, zero_casting=zero_casting
    )
    if spell_level > 0:
        maximum = record.get("maximum_level")
        if (
            type(maximum) is not int
            or not 1 <= maximum <= 32767
            or spell_level > maximum
        ):
            raise ValueError("Missing actual native scene spell level")
    row = record["levels"][index]
    if (
        not isinstance(row, (tuple, list))
        or len(row) != 3
        or not isinstance(row[2], list)
        or any(type(identity) is not int or identity <= 0 for identity in row[2])
    ):
        raise ValueError("Missing actual native scene casting roots")
    return row
