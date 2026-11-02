"""Bounded fight terrain selected from installed-client map exports."""
from wakfu_server import native_catalog as protocol_catalog
import json
import os
import random
import time
from wakfu_server.performance_profiler import PROFILER
from functools import lru_cache
from dataclasses import dataclass
from wakfu_server.paths import DATA_ROOT
from .combat_wire import arena
from .combat_arena_selection import (
    bounded_arena,
    full_room_encounter,
    compact_encounter,
    cardinal_border_cells,
)
from .combat_placement_cells import generate
from .combat_arena_interior import safe_interior
from .combat_geometry import published_geometry, prepare_geometry, coordinate
from .combat_qi_surface_catalog import native_qi_surfaces, native_qi_surface_provenance
from .combat_qi_surface_selection import native_surface_indices
from .combat_arena_empty_gaps import POLICY as EMPTY_GAP_POLICY, selected_gap_indices

SOURCE = DATA_ROOT / "amakna-test-arena.json"


@dataclass(frozen=True)
class PreparedTerrain:
    revision: str
    map_id: int
    geometry: object
    surfaces: object
    provenance: object


def prepare_terrain(map_id):
    """Retain complete validated static sources before gameplay row locks."""
    revision = protocol_catalog.release()
    geometry = published_geometry(map_id)
    surfaces = native_qi_surfaces(map_id)
    provenance = native_qi_surface_provenance(map_id)
    if protocol_catalog.release() != revision:
        raise ValueError("Native terrain catalog revision changed during preparation")
    return PreparedTerrain(revision, map_id, geometry, surfaces, provenance)


@lru_cache(maxsize=16)
def map_geometry(map_id):
    if type(map_id) is not int or map_id <= 0:
        raise ValueError("Invalid combat map identity")
    from wakfu_server.haven_world_terrain import TEMPLATE_MAP_ID, geometry

    if map_id == TEMPLATE_MAP_ID:
        if protocol_catalog.exists(DATA_ROOT / "combat-maps" / f"{map_id}.json"):
            raise ValueError(
                "Internal Haven World geometry namespace collides with native map"
            )
        return geometry()
    directory = DATA_ROOT / "combat-maps"
    for suffix in (".json",):
        path = directory / (str(map_id) + suffix)
        if protocol_catalog.exists(path):
            data = protocol_catalog.load(path)
            if data.get("map_id") != map_id:
                raise ValueError("Combat map export identity mismatch")
            return data
    raise ValueError("No installed-client geometry export for this map")


def local_arena(
    map_id,
    instance_id,
    player_position,
    monster_position,
    *,
    relocate_monsters=True,
    variation_seed=None,
    compact=None,
    minimum_dimensions=None,
    prepared_terrain=None,
    stage_callback=None,
    automatic_cell_budget=2500,
    size_range=(7, 20),
    allowed_cells=None,
    member_radii=None,
    player_radius=0,
    ordinary_npc_placement=False,
    full_room_scope=False,
    initial_obstacle_cells=(),
    fixed_member_positions=None,
):
    stage_started, stage_cpu = time.monotonic(), time.thread_time()

    def stage(name):
        nonlocal stage_started, stage_cpu
        now, cpu = time.monotonic(), time.thread_time()
        wall, consumed = now - stage_started, cpu - stage_cpu
        # Diagnostics must never reject an otherwise valid native arena.
        try:
            PROFILER.observe("combat.arena." + name, wall, consumed)
        except Exception:
            pass
        if stage_callback is not None:
            try:
                stage_callback(name, round(wall * 1000, 3), round(consumed * 1000, 3))
            except Exception:
                pass
        stage_started, stage_cpu = time.monotonic(), time.thread_time()

    if prepared_terrain is not None:
        if (
            not isinstance(prepared_terrain, PreparedTerrain)
            or prepared_terrain.map_id != map_id
            or prepared_terrain.revision != protocol_catalog.release()
        ):
            raise ValueError("Prepared terrain scope or catalog revision changed")
        geometry = prepared_terrain.geometry
        surfaces = prepared_terrain.surfaces
        provenance = prepared_terrain.provenance
    else:
        geometry = published_geometry(map_id)
        surfaces = None
        provenance = None
    if allowed_cells is not None:
        native = prepare_geometry(geometry)
        cells = frozenset(coordinate(cell) for cell in allowed_cells)
        if not cells or not cells.issubset(native.cells):
            raise ValueError("Combat room cells are absent from native terrain")
        geometry = prepare_geometry(
            dict(
                map_id=map_id,
                cells=cells,
                edges=tuple(
                    (start, end)
                    for start, end in native.edges
                    if start in cells and end in cells
                ),
            )
        )
    stage("geometry")
    if type(full_room_scope) is not bool or (full_room_scope and allowed_cells is None):
        raise ValueError("Full room scope requires explicit native room cells")
    if fixed_member_positions and not full_room_scope:
        raise ValueError("Fixed initial actors require full room placement")
    declared_obstacles = frozenset(coordinate(cell) for cell in initial_obstacle_cells)
    initial_obstacles = frozenset()
    if declared_obstacles:
        obstacle_geometry = prepare_geometry(geometry)
        if not declared_obstacles.issubset(obstacle_geometry.cells):
            raise ValueError("Authored initial obstacle leaves admitted native terrain")
        obstacle_columns = {cell[:2] for cell in declared_obstacles}
        initial_obstacles = frozenset(
            cell for cell in obstacle_geometry.cells if cell[:2] in obstacle_columns
        )
    if initial_obstacles and not full_room_scope:
        raise ValueError("Authored initial obstacles require full room placement")
    if full_room_scope:
        if compact is True:
            raise ValueError("Full room scope cannot use a compact arena")
        compact = False
    if compact is None:
        compact = relocate_monsters
    if type(compact) is not bool:
        raise ValueError("Invalid compact combat arena policy")
    members = monster_position
    if (
        isinstance(members, (tuple, list))
        and len(members) == 3
        and all(type(v) is int for v in members)
    ):
        members = [members]
    if allowed_cells is not None and any(
        coordinate(position) not in geometry.cells
        for position in [player_position, *members]
    ):
        raise ValueError("Combat participant is outside its pinned room")
    from .combat_placement_footprints import radii_for, covered_cells

    radii = radii_for(members, member_radii, player_radius)
    if type(ordinary_npc_placement) is not bool:
        raise ValueError("Invalid ordinary NPC placement policy")
    member_point_cells = None
    if ordinary_npc_placement:
        from .combat_sn_path import NativeSnColumns
        from .combat_walk_surface_policy import native_npc_point_placement_allowed

        columns = NativeSnColumns.from_published(map_id)
        physical_provenance = provenance or native_qi_surface_provenance(map_id)
        if columns.source_sha256 != physical_provenance.get("source_sha256"):
            raise ValueError("Native placement physical source differs from arena")
        member_point_cells = frozenset(
            cell
            for cell in prepare_geometry(geometry).cells
            if native_npc_point_placement_allowed(columns, cell)
        )
    placement_ground_cells = None
    if full_room_scope or compact:
        from .combat_ground_support import supported

        placement_provenance = provenance or native_qi_surface_provenance(map_id)
        placement_ground_cells = frozenset(
            cell
            for cell in prepare_geometry(geometry).cells
            if supported(map_id, cell, placement_provenance["source_sha256"])
        )
    configured_radius = int(os.environ.get("WAKFU_COMBAT_ARENA_RADIUS", "89"))
    if full_room_scope:
        selected = full_room_encounter(
            geometry,
            player_position,
            members,
            member_radii=radii,
            player_radius=player_radius,
            player_slots=6,
            member_point_cells=member_point_cells,
            reserved_cells=initial_obstacles,
            placement_ground_cells=placement_ground_cells,
            fixed_member_positions=fixed_member_positions,
        )
    elif compact:
        # Callers may supply a stable seed for retries; new fights vary by default.
        formation = random.Random(variation_seed)
        dimensions_include_border = minimum_dimensions is None
        if minimum_dimensions is None:
            if (
                not isinstance(size_range, (tuple, list))
                or len(size_range) != 2
                or any(type(value) is not int for value in size_range)
                or not 7 <= size_range[0] <= size_range[1] <= 50
            ):
                raise ValueError("Invalid combat arena size range")
            # Draw uniformly among feasible full-rectangle side lengths.
            maximum = min(size_range[1], int(automatic_cell_budget**0.5))
            if maximum < size_range[0]:
                raise ValueError("Combat arena minimum exceeds rectangle budget")
            minimum_width = minimum_height = formation.randint(size_range[0], maximum)
        else:
            minimum_width, minimum_height = minimum_dimensions

        def select_encounter(
            width, height, *, allow_border_footprints=False, player_slots=1
        ):
            return compact_encounter(
                geometry,
                player_position,
                members,
                minimum_cells=(width - 2) * (height - 2)
                if dimensions_include_border
                else width * height,
                minimum_dimensions=(width, height),
                dimensions_include_border=dimensions_include_border,
                member_radii=radii,
                player_radius=player_radius,
                spread_opponents=relocate_monsters,
                automatic_cell_budget=automatic_cell_budget,
                allow_border_footprints=allow_border_footprints,
                player_slots=player_slots,
                member_point_cells=member_point_cells,
                placement_ground_cells=placement_ground_cells,
            )

        selected_dimensions = minimum_width, minimum_height
        try:
            selected = select_encounter(minimum_width, minimum_height)
        except ValueError as error:
            if (
                not dimensions_include_border
                or str(error)
                != "Native arena lacks disjoint ordinary actor footprint capacity"
            ):
                raise
            # A random small crop must not reject a roster that fits the same
            # native room within the configured maximum side and cell budget.
            try:
                if (minimum_width, minimum_height) == (maximum, maximum):
                    raise error
                selected = select_encounter(maximum, maximum)
            except ValueError as maximum_error:
                if str(maximum_error) != str(error):
                    raise
                # Optional perimeter hazards cannot reject a complete native
                # body. safe_interior reserves these footprints before it
                # emits any border cells, without adding terrain or overlap.
                selected = select_encounter(
                    maximum, maximum, allow_border_footprints=True
                )
            selected_dimensions = maximum, maximum
        if not relocate_monsters and any(
            original != destination
            for original, destination in selected["participant_positions"]
        ):
            raise ValueError("Compact arena cannot preserve participant positions")
    else:
        selected = bounded_arena(
            geometry,
            player_position,
            members,
            radius=configured_radius,
        )
    if member_point_cells is not None and any(
        radius == 0 and destination not in member_point_cells
        for (_, destination), radius in zip(selected["participant_positions"], radii)
    ):
        raise ValueError("Ordinary NPC placement has no eligible native surface")

    def prepare_placement(selection):
        actual_positions = [
            pair[1] for pair in selection.get("participant_positions", [])
        ] or members
        footprints = set(
            covered_cells(
                tuple(
                    selection.get(
                        "participant_player_position",
                        (player_position, player_position),
                    )[1]
                ),
                player_radius,
                selection["cells"],
            )
        )
        if footprints & initial_obstacles:
            raise ValueError("Admission player overlaps an authored initial obstacle")
        footprints.update(initial_obstacles)
        for position, radius in zip(actual_positions, radii):
            occupied = covered_cells(tuple(position), radius, selection["cells"])
            if footprints & occupied:
                raise ValueError("Ordinary initial actor footprints overlap")
            footprints.update(occupied)
        stage("selection")
        perimeter = (
            cardinal_border_cells(selection["cells"]) if compact else frozenset()
        )
        interior, borders = safe_interior(
            selection["cells"],
            selection["edges"],
            selection["placement"],
            perimeter,
            reserved_cells=footprints,
            placement_capacity=sum(
                max(12, len(team)) for team in selection["placement"].values()
            ),
        )
        placement = generate(
            interior,
            tuple(
                (start, end)
                for start, end in selection["edges"]
                if start in interior
                and end in interior
                and start not in initial_obstacles
                and end not in initial_obstacles
                and (
                    placement_ground_cells is None
                    or (
                        start in placement_ground_cells
                        and end in placement_ground_cells
                    )
                )
            ),
            seeds=selection["placement"],
            slots_per_team=12,
            avoid_cells=(),
            spread_teams=True,
            occupied_cells=footprints
            | (
                set(interior) - placement_ground_cells
                if placement_ground_cells is not None
                else set()
            ),
        )
        # Placement and both teams share the same native hazard-free component.
        # The complete arena remains available for movement and native effects.
        stage("placement")
        return borders, placement

    borders, placement = prepare_placement(selected)
    if compact and dimensions_include_border and len(placement[0]) < 6:
        # Keep room for a complete party when a random crop strands the player
        # in a narrow pocket. A larger crop must improve the existing safe zone.
        larger_available = True
        try:
            if selected_dimensions == (maximum, maximum):
                candidate = selected
            else:
                candidate = select_encounter(maximum, maximum)
        except ValueError as error:
            if str(error) != (
                "Native arena lacks disjoint ordinary actor footprint capacity"
            ):
                larger_available = False
            else:
                try:
                    candidate = select_encounter(
                        maximum, maximum, allow_border_footprints=True
                    )
                except ValueError:
                    larger_available = False
        if larger_available:
            try:
                candidate_borders, candidate_placement = prepare_placement(candidate)
            except ValueError:
                larger_available = False
            else:
                if len(candidate_placement[0]) > len(placement[0]):
                    selected = candidate
                    borders, placement = candidate_borders, candidate_placement
        if larger_available and len(placement[0]) < 6:
            try:
                try:
                    candidate = select_encounter(maximum, maximum, player_slots=6)
                except ValueError as error:
                    if str(error) != (
                        "Native arena lacks disjoint ordinary actor footprint capacity"
                    ):
                        raise
                    candidate = select_encounter(
                        maximum,
                        maximum,
                        allow_border_footprints=True,
                        player_slots=6,
                    )
                candidate_borders, candidate_placement = prepare_placement(candidate)
            except ValueError:
                # Geometry is already validated. An optional larger party
                # reservation must retain the proven encounter if it cannot fit.
                pass
            else:
                if len(candidate_placement[0]) > len(placement[0]):
                    selected = candidate
                    borders, placement = candidate_borders, candidate_placement
    if surfaces is None:
        surfaces = native_qi_surfaces(map_id)
    stage("surface_catalog")
    indices = native_surface_indices(surfaces, selected["cells"])
    stage("surface_indices")
    # Native empty water columns stay unwalkable without becoming solid LOS walls.
    gap_indices = selected_gap_indices(map_id, selected["cells"], EMPTY_GAP_POLICY)
    result = arena(
        map_id,
        instance_id,
        sorted(selected["cells"]),
        placement,
        surface_indices=indices,
        native_surfaces=surfaces,
        border_cells=borders,
        gap_surface_indices=gap_indices,
    )
    result.update(
        validated_cells=selected["cells"],
        valid_edges=selected["edges"],
        placement_cells=placement,
        native_qi_surface_provenance=native_qi_surface_provenance(map_id)
        if provenance is None
        else provenance,
        participant_positions=selected.get("participant_positions", []),
        native_los_gap_policy=EMPTY_GAP_POLICY,
        native_los_gap_surfaces=[
            [x, y, index] for (x, y), index in sorted(gap_indices.items())
        ],
        native_border_cells=borders,
        native_border_policy="wakemu.compact-cardinal-perimeter-v1"
        if compact
        else None,
    )
    if full_room_scope:
        result["native_full_room_scope"] = True
        for key in ("participant_player_position", "native_initial_player_relocation"):
            if key in selected:
                result[key] = selected[key]
    if selected.get("party_reserved_cells"):
        result["native_party_reserved_cells"] = [
            list(cell) for cell in selected["party_reserved_cells"]
        ]
        npc_cells = set()
        for position, radius in zip(
            (pair[1] for pair in selected["participant_positions"]), radii
        ):
            npc_cells.update(covered_cells(position, radius, selected["cells"]))
        if npc_cells & set(selected["party_reserved_cells"]):
            raise ValueError("Ordinary party reservation overlaps native NPC bodies")
        result["native_party_npc_cells"] = [list(cell) for cell in sorted(npc_cells)]
    stage("wire")
    return result
