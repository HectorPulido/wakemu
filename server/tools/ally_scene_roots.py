"""Use native casting roots at resolved PL, not sampled effect-tree levels."""


def native_ally_scene_roots(spell, spell_level, casting, effects):
    from native_scene_casting import native_scene_casting_row

    row = native_scene_casting_row(spell, spell_level, casting)
    if any(str(identity) not in effects for identity in row[2]):
        raise ValueError("Missing actual native ally scene root definition")
    return [effects[str(identity)] for identity in row[2]]
