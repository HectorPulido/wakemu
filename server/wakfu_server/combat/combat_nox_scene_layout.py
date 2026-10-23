"""Database-reviewed Nox initial markers on unchanged native map1435 terrain.

The guide establishes eleven artifacts, five batteries and one cube, not XYZ.
Database coordinates are explicit Wakemu placement reconstruction. Native
prototypes retain their pickup criteria, properties, effects and event masks.
"""
from .combat_geometry import prepare_geometry, reachable


MAP_ID = 1435
REFERENCE = 5664
POLICY = "wakemu.nox.initial-artifacts.native-floor-reconstruction.v1"
AUTHORITY = "authorized_wakemu_initial_artifact_placement_reconstruction"
OBSERVATION_URL = "https://methodwakfu.com/pvm/boss-ultimes/coeur-de-lhorloge-de-nox/"
BOSS_CELL = (-1, -17, 0)
PARTY_CELLS = (
    (-1, -7, 0),
    (-7, -7, 0),
    (-4, -7, 0),
    (2, -7, 0),
    (5, -7, 0),
    (-1, -6, 0),
)


def reconstructed_nox_scene(geometry):
    """Declare initial neutral faY objects before actors and initial events."""
    from .combat_arena_selection import cardinal_border_cells
    from .combat_battleground_border import DECLARED_COMPONENT_POLICY
    from .combat_encounter_marker_placements import active_marker_placements

    native = prepare_geometry(geometry)
    if native.map_id != MAP_ID:
        raise ValueError("Nox reconstructed scene requires native map1435")
    marker_policy = active_marker_placements(MAP_ID, (REFERENCE,))
    declarations = marker_policy.declarations()
    candidates = frozenset(
        cell for cell in native.cells if cell[2] == 0 and cell[1] <= -5
    )
    if PARTY_CELLS[0] not in candidates:
        raise ValueError("Native Nox chamber lacks the reconstructed party anchor")
    board = reachable(PARTY_CELLS[0], candidates, native.outgoing) & reachable(
        PARTY_CELLS[0], candidates, native.incoming
    )
    footprint = frozenset(
        (BOSS_CELL[0] + dx, BOSS_CELL[1] + dy, 0)
        for dx in (-1, 0, 1)
        for dy in (-1, 0, 1)
    )
    glyphs = tuple(tuple(row["cell"]) for row in declarations)
    if (
        len(board) < 200
        or not footprint <= board
        or not set((*PARTY_CELLS, *glyphs)) <= board
        or len(set(glyphs)) != len(glyphs)
        or set(glyphs) & (set(PARTY_CELLS) | footprint)
        or set(PARTY_CELLS) & footprint
    ):
        raise ValueError("Native Nox chamber cannot support the declared initial scene")
    floor = board - footprint
    reached = reachable(PARTY_CELLS[0], floor, native.outgoing)
    if not set((*PARTY_CELLS, *glyphs)) <= reached:
        raise ValueError("Declared Nox artifacts are unreachable on native edges")
    border = cardinal_border_cells(board)
    if border & (set(PARTY_CELLS) | set(glyphs) | footprint):
        raise ValueError("Declared Nox slots overlap the native chamber perimeter")
    return dict(
        policy=POLICY,
        route_key=POLICY,
        authority=AUTHORITY,
        observation_url=OBSERVATION_URL,
        original_world_coordinates=False,
        map_id=MAP_ID,
        reference=REFERENCE,
        source=BOSS_CELL,
        caster_cell=BOSS_CELL,
        anchor=PARTY_CELLS[0],
        party_placement_cells=PARTY_CELLS,
        boss_footprint=footprint,
        boss_direction=3,
        glyph_cells=glyphs,
        cells=frozenset(board),
        edges=frozenset((a, b) for a, b in native.edges if a in board and b in board),
        native_border_scope_cells=frozenset(board),
        native_border_cells=border,
        native_border_policy=DECLARED_COMPONENT_POLICY,
        native_initial_glyphs=declarations,
        native_initial_glyph_policy=marker_policy.policy,
        native_initial_glyph_authority=marker_policy.authority,
        native_initial_glyph_source_url=marker_policy.source_url,
        setup_scope="initial_markers_original_artifacts_battery_and_cube_producers",
        complete_encounter_qualified=False,
    )
