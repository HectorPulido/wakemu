"""Reconstructed aerial boss placements on existing native islands.

Guide images identify separate aerial platforms, not world coordinates. These
policies fit that observation to exported terrain. Disconnected platforms stay
disconnected: phase movement belongs to native effects, never fabricated edges.
"""
from .combat_geometry import encounter_component, prepare_geometry, reachable


AUTHORITY = "reconstructed_world_coordinates_from_observed_platform_layout"
CROW_OBSERVATION_URL = (
    "https://methodwakfu.com/wp-content/uploads/2019/03/Position-de-d-part.jpg"
)
STEEL_OBSERVATION_URL = (
    "https://methodwakfu.com/wp-content/uploads/2019/04/Zone_Safe.png"
)
CROW_BOSS = (-6, -17, 88)
CROW_ANCHOR = (-7, 0, 88)
STEEL_BOSSES = {"left": (-17, 3, 0), "right": (-1, -13, 0)}
STEEL_ANCHOR = (-7, 3, 0)


def _footprint(center):
    return frozenset(
        (center[0] + dx, center[1] + dy, center[2])
        for dx in range(-1, 2)
        for dy in range(-1, 2)
    )


def _scene(geometry, *, map_id, anchor, boss, platforms, policy, observation_url):
    native = prepare_geometry(geometry)
    if native.map_id != map_id:
        raise ValueError(f"Reconstructed scene requires native map{map_id}")
    board, _ = encounter_component(native, anchor)
    footprints = tuple(_footprint(center) for center in platforms)
    aerial = frozenset().union(*footprints)
    if not aerial <= native.cells or aerial & board:
        raise ValueError(
            "Native terrain lacks separate complete aerial boss footprints"
        )
    # Every platform must itself support the nine cells in both directions.
    for center, footprint in zip(platforms, footprints):
        if (
            reachable(center, footprint, native.outgoing) != footprint
            or reachable(center, footprint, native.incoming) != footprint
        ):
            raise ValueError("Native aerial boss footprint is not mutually reachable")
    eligible = set()
    for cell in board:
        if cell[2] != anchor[2]:
            continue
        neighbors = {
            (cell[0] + dx, cell[1] + dy, cell[2])
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
        }
        if (
            neighbors <= board
            and neighbors <= set(native.outgoing.get(cell, ()))
            and neighbors <= set(native.incoming.get(cell, ()))
        ):
            eligible.add(cell)
    if anchor not in eligible:
        raise ValueError("Reconstructed party anchor is not an interior native cell")
    party = []
    for cell in sorted(
        eligible, key=lambda c: (abs(c[0] - anchor[0]) + abs(c[1] - anchor[1]), c)
    ):
        if all(
            abs(cell[0] - other[0]) + abs(cell[1] - other[1]) >= 3 for other in party
        ):
            party.append(cell)
            if len(party) == 6:
                break
    if len(party) != 6:
        raise ValueError("Native board lacks six separated interior party cells")
    cells = frozenset(board) | aerial
    edges = frozenset((a, b) for a, b in native.edges if a in cells and b in cells)
    return dict(
        policy=policy,
        route_key=policy,
        authority=AUTHORITY,
        observation_url=observation_url,
        original_world_coordinates=False,
        map_id=map_id,
        source=boss,
        caster_cell=boss,
        anchor=anchor,
        cells=cells,
        edges=edges,
        party_placement_cells=tuple(party),
        boss_footprint=_footprint(boss),
        aerial_platform_cells=aerial,
        main_board_cells=frozenset(board),
    )


def reconstructed_crow_scene(geometry):
    """Place Black Crow on the observed separate platform near the main board."""
    scene = _scene(
        geometry,
        map_id=363,
        anchor=CROW_ANCHOR,
        boss=CROW_BOSS,
        platforms=(CROW_BOSS,),
        policy="wakemu.crow.observed_native_aerial_platform.v1",
        observation_url=CROW_OBSERVATION_URL,
    )
    # The guide observes a landing on the main board, without world positions.
    # Select an actual clear nine-cell landing footprint nearest its centroid.
    board = scene["main_board_cells"]
    party = set(scene["party_placement_cells"])
    count = len(board)
    sx, sy = sum(c[0] for c in board), sum(c[1] for c in board)
    candidates = [
        cell
        for cell in board
        if _footprint(cell) <= board and not _footprint(cell) & party
    ]
    if not candidates:
        raise ValueError("Native Crow board lacks a clear landing footprint")
    landing = min(
        candidates,
        key=lambda c: ((count * c[0] - sx) ** 2 + (count * c[1] - sy) ** 2, c),
    )
    scene.update(
        native_initial_glyphs=[dict(reference=1724, cell=list(landing), level=0)],
        native_initial_glyph_policy="wakemu.crow.reconstructed-main-board-landing.v1",
        native_initial_glyph_authority=AUTHORITY,
        native_initial_glyph_source_url=CROW_OBSERVATION_URL,
    )
    from .combat_arena_empty_gaps import TRANSPARENT_VOID_POLICY

    scene["native_los_gap_policy"] = TRANSPARENT_VOID_POLICY
    return scene


def reconstructed_steel_scene(geometry, side="left"):
    """Keep both native platforms; choose the initial side before Actor creation."""
    if side not in STEEL_BOSSES:
        raise ValueError("Steel Beak initial side must be left or right")
    scene = _scene(
        geometry,
        map_id=959,
        anchor=STEEL_ANCHOR,
        boss=STEEL_BOSSES[side],
        platforms=tuple(STEEL_BOSSES.values()),
        policy="wakemu.steel.observed_native_aerial_platforms.v1",
        observation_url=STEEL_OBSERVATION_URL,
    )
    from .combat_arena_selection import cardinal_border_cells
    from .combat_battleground_border import DECLARED_COMPONENT_POLICY
    from .combat_arena_empty_gaps import POLICY as EMPTY_GAP_POLICY

    # Aerial islands remain selected terrain, outside the board's cliff scope.
    scene.update(
        # Original152475/152479 directional point producers must reach the
        # opposite native platform before any actors or areas are created.
        boss_direction=1 if side == "left" else 3,
        terrain_effect_id=909,
        native_border_scope_cells=scene["main_board_cells"],
        native_border_cells=cardinal_border_cells(scene["main_board_cells"]),
        native_border_policy=DECLARED_COMPONENT_POLICY,
        native_los_gap_policy=EMPTY_GAP_POLICY,
    )
    return scene
