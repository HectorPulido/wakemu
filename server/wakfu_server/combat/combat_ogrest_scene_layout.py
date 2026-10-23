"""Explicit Ogrest reconstruction on the first original raised arena copy.

The source map contains several disconnected arenas and duplicates. Select
one native component by its declared landmarks, never by global size. Artifact
coordinates are Wakemu content policy, not recovered publisher coordinates.
"""
from .combat_geometry import prepare_geometry


OGREST_LAYOUT_POLICY = "wakemu.ogrest.native-raised-arena.v1"


def reconstructed_ogrest_scene(geometry):
    from .combat_supreme_scene_policies import _component, _layout

    native = prepare_geometry(geometry)
    if native.map_id != 1156:
        raise ValueError("Ogrest requires its original native map1156")
    source, anchor = (0, -30, 40), (3, -24, 40)
    first_arena = frozenset(
        cell for cell in native.cells if -12 <= cell[0] <= 14 and -44 <= cell[1] <= -17
    )
    board = _component(native, anchor, allowed=first_arena)
    if len(board) != 554 or source not in board:
        raise ValueError("Ogrest raised arena component changed")
    result = _layout(native, 4378, board, source, anchor)
    columns = {}
    for cell in board:
        columns.setdefault(cell[:2], []).append(cell)
    # Ten original pickup types are offered, one per actual native column.
    # Retain native rock-step heights on the connected pickup floor.
    cells = []
    for x in range(-4, 6):
        choices = columns.get((x, -21), ())
        if len(choices) != 1:
            raise ValueError("Ogrest artifact column is absent or ambiguous")
        cells.append(choices[0])
    # Native Purple6186 starts with three forward fire rays through x=-1,0,1.
    # Preserve those hazards and put the declared initial party beside them.
    # All floor cells remain available to the original damage selectors.
    reached = _component(native, anchor, allowed=board - result["boss_footprint"])
    candidates = [
        cell
        for cell in reached
        if cell not in cells
        and not (-1 <= cell[0] <= 1 and cell[1] >= -28)
        and sum(
            (cell, adjacent) in native.edges and adjacent in reached
            for adjacent in (
                (cell[0] + 1, cell[1], cell[2]),
                (cell[0] - 1, cell[1], cell[2]),
                (cell[0], cell[1] + 1, cell[2]),
                (cell[0], cell[1] - 1, cell[2]),
            )
        )
        >= 3
    ]
    party = tuple(
        sorted(
            candidates,
            key=lambda cell: (
                abs(cell[0] - anchor[0])
                + abs(cell[1] - anchor[1])
                + abs(cell[2] - anchor[2]),
                cell,
            ),
        )[:15]
    )
    if len(party) != 15 or anchor not in party:
        raise ValueError("Ogrest opening lacks its native safe party formation")
    result["party_placement_cells"] = party
    if set(cells) & (set(party) | set(result["boss_footprint"])):
        raise ValueError("Ogrest artifacts overlap its initial fighter formation")
    result.update(
        policy=OGREST_LAYOUT_POLICY,
        route_key=OGREST_LAYOUT_POLICY,
        glyph_cells=tuple(cells),
        artifact_placement_policy="ten_original_types_on_declared_native_columns",
        initial_artifact_references=tuple(range(1213, 1223)),
        native_initial_glyphs=tuple(
            dict(reference=reference, level=1, cell=list(cell))
            for reference, cell in zip(range(1213, 1223), cells)
        ),
        native_initial_glyph_policy="wakemu.ogrest.initial-artifacts.v1",
        native_initial_glyph_authority="authorized_wakemu_content_reconstruction",
        native_initial_glyph_source_url="https://wakfu.guide/ogrest/",
        setup_scope="native_terrain_and_artifact_plan_phase_controller_not_yet_qualified",
    )
    return result
