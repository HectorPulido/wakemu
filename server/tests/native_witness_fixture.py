"""Source-bound native placement and normal level200 player fixture creation."""
import hashlib
import inspect


def legal_witness_cell():
    """Choose a distant local cell only after the actual arena preserves it."""
    from wakfu_server.combat_geometry import published_geometry
    from wakfu_server.combat_terrain import local_arena

    source = (-8, -7, -1)
    cells = published_geometry(1134).cells
    candidates = sorted(
        (
            c
            for c in cells
            if c != source and 2 <= abs(c[0] - source[0]) + abs(c[1] - source[1]) <= 6
        ),
        key=lambda c: (abs(c[0] - source[0]) + abs(c[1] - source[1]), c),
        reverse=True,
    )
    errors = []
    # Include the already-executed ordinary scene as a genuine fallback.
    fallback = (-10, -7, -1)
    candidates = candidates[:24] + ([fallback] if fallback in cells else [])
    for cell in candidates:
        try:
            arena = local_arena(
                1134,
                0,
                cell,
                source,
                relocate_monsters=False,
                compact=True,
                variation_seed=1,
                minimum_dimensions=(9, 9),
            )
            borders = arena["native_border_cells"]
            if source in borders or cell in borders:
                raise ValueError("Witness placement is on the native border")
            return cell, {
                "source": list(source),
                "enemy": list(cell),
                "manhattan_distance": abs(cell[0] - source[0])
                + abs(cell[1] - source[1]),
                "native_arena_cells": len(arena["validated_cells"]),
                "preservation": "Actual local_arena compact9x9, relocate_monsters=False",
                "prior_selection_errors": errors,
            }
        except ValueError as error:
            errors.append({"cell": list(cell), "error": str(error)})
    raise ValueError(
        "No source-preserving native local witness placement: " + repr(errors)
    )


def native_level200_fixture(validator):
    """Change only the fixture's default BEFORE ordinary player construction.

    The normal source constructors calculate level200 HP/resources/Actor and
    class initialization. This does not mutate an existing actor or grant
    state, AP, MP or WP. XP is the actual native threshold for that level.
    """
    from wakfu_server.progression import level_xp

    original = inspect.getsource(validator.fixture)
    before = 'character_level = buff_recipe["character_level"] if buff_recipe else 1'
    after = 'character_level = buff_recipe["character_level"] if buff_recipe else 200'
    assert original.count(before) == 1, "Native fixture default level source drift"
    modified = original.replace(before, after)
    anchor = "            level=character_level,\n"
    assert modified.count(anchor) == 1, "Native fixture character construction drift"
    modified = modified.replace(
        anchor, anchor + "            xp=_witness_native_level_xp(character_level),\n"
    )
    namespace = dict(validator.fixture.__globals__)
    namespace["_witness_native_level_xp"] = level_xp
    exec(compile(modified, "<private-native-level200-fixture>", "exec"), namespace)
    facts = {
        "base_fixture_source_sha256": hashlib.sha256(original.encode()).hexdigest(),
        "fixture_source_sha256": hashlib.sha256(modified.encode()).hexdigest(),
        "default_character_level": 200,
        "native_xp_threshold": level_xp(200),
        "scope": "Normal owned level200 player fixture constructed from native XP/health/resources; no post-construction state/resource writes.",
    }
    return namespace["fixture"], facts
