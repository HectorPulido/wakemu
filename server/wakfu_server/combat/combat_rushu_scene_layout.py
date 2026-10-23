"""Explicit Wakemu Rushu scene, fitted to observed relative placement.

The community schematic supplies relative cells, not original world coordinates.
This policy translates them onto existing map1332 terrain; it never adds cells,
edges, Qq instances, actors, states or resources to the native geometry.
"""
from collections import defaultdict, deque

from .combat_geometry import prepare_geometry


POLICY = "wakemu.rushu.observed_schematic_native_floor_translation.v1"
AUTHORITY = "reconstructed_world_coordinates_from_observed_relative_schematic"
OBSERVATION_URL = (
    "https://methodwakfu.com/wp-content/uploads/2026/07/Rushu-arene-schema.png"
)
MAP_ID = 1332
BOSS_CELL = (-49, 7, -4)
PLAYER_CELL = (-39, 7, -4)
# Fixed slots observed in the schematic. Glyph types are independently shuffled
# by the encounter setup; their order here must not imply native type assignment.
GLYPH_OFFSETS = (
    (0, -3),
    (0, 3),
    (1, 7),
    (2, -6),
    (3, -1),
    (3, 1),
    (3, 5),
    (5, -6),
    (5, 4),
    (7, -2),
    (7, 2),
    (8, -5),
    (11, 7),
    (13, -5),
    (14, -2),
    (14, 7),
)
PARTY_OFFSETS = (
    (10, -3),
    (10, -1),
    (10, 0),
    (10, 1),
    (10, 3),
    (11, -5),
    (11, 5),
    (12, -4),
    (12, -3),
    (12, -1),
    (12, 0),
    (12, 1),
    (12, 3),
    (12, 4),
    (14, 0),
)


def _translate(offsets):
    return tuple((BOSS_CELL[0] + x, BOSS_CELL[1] + y, BOSS_CELL[2]) for x, y in offsets)


def reconstructed_scene(geometry):
    """Select and validate the reconstructed room from authoritative terrain.

    Native cells and directed edges stay unchanged. Both the boss and players
    must use these scene inputs before Actor construction. This is a scene
    policy, not a claim that the installed map exports original combat spawns.
    """
    from .combat_arena_selection import cardinal_border_cells

    native = prepare_geometry(geometry)
    if native.map_id != MAP_ID:
        raise ValueError("Rushu reconstructed scene requires native map1332")
    cells = frozenset(
        cell
        for cell in native.cells
        if -55 <= cell[0] <= -33 and -3 <= cell[1] <= 17 and cell[2] == -4
    )
    edges = frozenset(
        (start, end) for start, end in native.edges if start in cells and end in cells
    )
    glyphs = _translate(GLYPH_OFFSETS)
    party = _translate(PARTY_OFFSETS)
    footprint = frozenset(
        (BOSS_CELL[0] + dx, BOSS_CELL[1] + dy, BOSS_CELL[2])
        for dx in range(-1, 2)
        for dy in range(-1, 2)
    )
    if not footprint <= cells:
        raise ValueError(
            "Native terrain cannot support the reconstructed boss footprint"
        )
    if len(set(glyphs)) != 16 or len(set(party)) != 15:
        raise ValueError("Reconstructed Rushu observed slots are not unique")
    if not set(glyphs) <= cells or not set(party) <= cells or PLAYER_CELL not in party:
        raise ValueError("Native terrain lacks a required reconstructed Rushu slot")
    if set(glyphs) & set(party) or footprint & (set(glyphs) | set(party)):
        raise ValueError("Reconstructed Rushu slots overlap the initial boss or party")
    border = cardinal_border_cells(cells)
    if border & (set(glyphs) | set(party) | footprint):
        raise ValueError(
            "Reconstructed Rushu perimeter overlaps initial encounter slots"
        )
    adjacency = defaultdict(list)
    for start, end in sorted(edges):
        adjacency[start].append(end)
    distances = {PLAYER_CELL: 0}
    pending = deque((PLAYER_CELL,))
    while pending:
        source = pending.popleft()
        for target in adjacency[source]:
            if target not in footprint and target not in distances:
                distances[target] = distances[source] + 1
                pending.append(target)
    if any(cell not in distances for cell in (*glyphs, *party)):
        raise ValueError(
            "A reconstructed Rushu slot is unreachable on native directed terrain"
        )
    return dict(
        policy=POLICY,
        authority=AUTHORITY,
        observation_url=OBSERVATION_URL,
        original_world_coordinates=False,
        map_id=MAP_ID,
        route_key=POLICY,
        source=BOSS_CELL,
        caster_cell=BOSS_CELL,
        anchor=PLAYER_CELL,
        cells=cells,
        edges=edges,
        glyph_cells=glyphs,
        party_placement_cells=party,
        boss_footprint=footprint,
        glyph_route_lengths=tuple(distances[cell] for cell in glyphs),
        native_border_cells=border,
        native_border_policy="wakemu.reconstructed-native-cardinal-perimeter-v1",
        terrain_effect_id=378,
    )
