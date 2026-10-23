"""Reconstructed native encounter inputs; original Ready runners own all actors.

Absolute positions are Wakemu policy on exported terrain, not recovered original
spawns. Foul Moon's native point groups place its totems. Tal Kasha's five static
marker prototypes are separate from its native pyramid/mirror summon runners.
"""
from collections import deque

from .combat_geometry import prepare_geometry


FULMOON_POLICY = "wakemu.fulmoon.native_ready_point_fit.v3"
TALKASHA_POLICY = "wakemu.talkasha.native_marker_fit.v4"
FULMOON_POINT_GROUPS = (177762, 177776, 177778, 177780, 177782)
TALKASHA_MARKERS = (
    (1837, (-3, -38, -22)),
    (1837, (3, -38, -22)),
    (1837, (0, -41, -22)),
    (1837, (0, -35, -22)),
    (1838, (0, -38, -22)),
)


def _component(native, origin, allowed=None):
    allowed = native.cells if allowed is None else frozenset(allowed)
    if origin not in allowed:
        raise ValueError("Encounter origin is absent from native terrain")
    seen, queue = {origin}, deque((origin,))
    while queue:
        for point in native.outgoing.get(queue.popleft(), ()):
            if point in allowed and point not in seen:
                seen.add(point)
                queue.append(point)
    return frozenset(seen)


def _profile(reference):
    from wakfu_server import native_catalog
    from wakfu_server.paths import DATA_ROOT

    profile = native_catalog.record(
        DATA_ROOT / "native-actor-characteristics.json", "npc_profiles", str(reference)
    )
    if (
        not isinstance(profile, dict)
        or type(profile.get("physical_radius")) is not int
        or profile["physical_radius"] != 0
    ):
        raise ValueError(
            "Reconstructed scene requires its verified native radius0 profile"
        )
    return profile


def _layout(native, reference, source, anchor, cells, reserved, *, policy, url):
    from .combat_obstacle_condition import footprint

    _profile(reference)
    cells = frozenset(cells)
    reserved = frozenset(reserved)
    boss = frozenset((x, y, source[2]) for x, y in footprint(source, 0))
    if not (reserved | boss | {anchor}) <= cells or reserved & (boss | {anchor}):
        raise ValueError("Native encounter inputs overlap or leave their actual floor")
    available = _component(native, anchor, cells - reserved - boss)
    party = tuple(
        sorted(
            available,
            key=lambda point: (
                abs(point[0] - anchor[0])
                + abs(point[1] - anchor[1])
                + abs(point[2] - anchor[2]),
                point,
            ),
        )[:15]
    )
    if len(party) < 6 or anchor not in party:
        raise ValueError("Native encounter lacks six unoccupied player slots")
    return dict(
        policy=policy,
        route_key=policy,
        reference=reference,
        authority="authorized_wakemu_native_content_reconstruction",
        observation_url=url,
        original_world_coordinates=False,
        map_id=native.map_id,
        source=source,
        caster_cell=source,
        anchor=anchor,
        cells=cells,
        edges=frozenset((a, b) for a, b in native.edges if a in cells and b in cells),
        party_placement_cells=party,
        boss_footprint=boss,
        boss_direction=3,
        glyph_cells=tuple(sorted(reserved)),
        complete_encounter_qualified=False,
    )


def fulmoon_ready_cells(source):
    """Reserve original group outputs after native177764 orientation mode3."""
    from wakfu_server import native_catalog
    from wakfu_server.paths import DATA_ROOT
    from .combat_native_area_metadata import merge_native_point_areas
    from .combat_group_cells import ordered_offsets
    from .combat_orientation_effect import MODES

    effects = {}
    facing = native_catalog.record(
        DATA_ROOT / "native-npc-spell-effect-trees.json", "effects", "177764"
    )
    if (
        not isinstance(facing, dict)
        or facing.get("effect_class") != 303
        or facing.get("parameters") != [3.0, 0.0]
    ):
        raise ValueError("Foul Moon native Ready facing contract changed")
    direction = MODES[int(facing["parameters"][0])]
    for reference in FULMOON_POINT_GROUPS:
        effect = native_catalog.record(
            DATA_ROOT / "native-npc-spell-effect-trees.json", "effects", str(reference)
        )
        if (
            not isinstance(effect, dict)
            or effect.get("effect_class") != 330
            or effect.get("area_class") != "anE"
            or effect.get("parameters", [])[4:5] != [0.0]
            or effect.get("native_target_selector") != {"class": "fcE", "mask": 1}
        ):
            raise ValueError("Foul Moon native Ready point-group contract changed")
        effects[str(reference)] = effect
    merged = merge_native_point_areas(effects)
    targets = {}
    for reference in FULMOON_POINT_GROUPS:
        offsets = ordered_offsets(
            merged[str(reference)], origin=source, reference=source, direction=direction
        )
        if len(offsets) != 1:
            raise ValueError(
                "Foul Moon initial group no longer selects one original cell"
            )
        dx, dy = offsets[0]
        targets[reference] = (source[0] + dx, source[1] + dy, source[2])
    if len(set(targets.values())) != 5:
        raise ValueError("Foul Moon original Ready cells are not distinct")
    return targets


def reconstructed_fulmoon_scene(geometry):
    native = prepare_geometry(geometry)
    if native.map_id != 1056:
        raise ValueError("Foul Moon scene requires native map1056")
    # Mode3 sets native facing1. All five original offsets fit the interior;
    # source(0,1,0) placed the earth totem on the native cardinal perimeter.
    source, anchor = (0, 0, 0), (1, 0, 0)
    cells = _component(native, (9, 1, 0))
    targets = fulmoon_ready_cells(source)
    layout = _layout(
        native,
        3870,
        source,
        anchor,
        cells,
        targets.values(),
        policy=FULMOON_POLICY,
        url="https://wakfulabs.com/dungeons/boss-ultimes/cime-grand-totem/",
    )
    from .combat_arena_selection import cardinal_border_cells
    from .combat_battleground_border import DECLARED_COMPONENT_POLICY

    border = cardinal_border_cells(cells)
    occupied = (
        set(layout["party_placement_cells"])
        | set(targets.values())
        | set(layout["boss_footprint"])
    )
    if border & occupied:
        raise ValueError("Foul Moon actors or original Ready outputs touch the border")
    layout.update(
        terrain_effect_id=1085,
        native_border_scope_cells=cells,
        native_border_cells=border,
        native_border_policy=DECLARED_COMPONENT_POLICY,
    )
    layout[
        "setup_scope"
    ] = "native1085_border_and1003_four_totems_and1086_no_manual_actor_seed"
    return layout


def reconstructed_talkasha_scene(geometry):
    native = prepare_geometry(geometry)
    if native.map_id != 1400:
        raise ValueError("Tal Kasha scene requires native map1400")
    source, anchor = (1, -33, -22), (0, -34, -22)
    # Use only the actual lower arena floor; the stairs remain exploration terrain.
    floor = frozenset(point for point in native.cells if point[2] == -22)
    reachable = _component(native, anchor, floor)
    # Keep original physical surfaces in this room, including isolated ones.
    # Original edges still govern traversal; the distant room stays excluded.
    x0, x1 = min(cell[0] for cell in reachable), max(cell[0] for cell in reachable)
    y0, y1 = min(cell[1] for cell in reachable), max(cell[1] for cell in reachable)
    cells = frozenset(
        cell for cell in floor if x0 <= cell[0] <= x1 and y0 <= cell[1] <= y1
    )
    layout = _layout(
        native,
        5500,
        source,
        anchor,
        cells,
        (point for reference, point in TALKASHA_MARKERS),
        policy=TALKASHA_POLICY,
        url="https://wakfu.guide/talkasha/",
    )
    layout.update(
        native_surface_envelope_policy="native_component_bounds_same_floor",
        isolated_native_surfaces=tuple(sorted(cells - reachable)),
        native_initial_glyphs=[
            dict(reference=reference, cell=list(point))
            for reference, point in TALKASHA_MARKERS
        ],
        native_initial_glyph_policy="wakemu.talkasha.reconstructed-aligned-initial-markers.v3",
        native_initial_glyph_authority="authorized_wakemu_native_prototype_bootstrap_original_owner_unrecovered",
        native_initial_glyph_source_url="https://wakfu.guide/talkasha/",
    )
    layout["setup_scope"] = "five_native_marker_prototypes_before_original1003_summons"
    return layout
