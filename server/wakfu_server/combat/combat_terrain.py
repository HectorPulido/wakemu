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
    compact_encounter,
    cardinal_border_cells,
)
from .combat_placement_cells import generate
from .combat_arena_interior import safe_interior
from .combat_geometry import published_geometry, prepare_geometry, coordinate
from .combat_qi_surface_catalog import native_qi_surfaces, native_qi_surface_provenance
from .combat_qi_surface_selection import native_surface_indices

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
    configured_radius = int(os.environ.get("WAKFU_COMBAT_ARENA_RADIUS", "89"))
    if compact:
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
        selected = compact_encounter(
            geometry,
            player_position,
            members,
            minimum_cells=(minimum_width - 2) * (minimum_height - 2)
            if dimensions_include_border
            else minimum_width * minimum_height,
            minimum_dimensions=(minimum_width, minimum_height),
            dimensions_include_border=dimensions_include_border,
            member_radii=radii,
            player_radius=player_radius,
            spread_opponents=relocate_monsters,
            automatic_cell_budget=automatic_cell_budget,
        )
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
    actual_positions = [
        pair[1] for pair in selected.get("participant_positions", [])
    ] or members
    footprints = set(
        covered_cells(tuple(player_position), player_radius, selected["cells"])
    )
    for position, radius in zip(actual_positions, radii):
        occupied = covered_cells(tuple(position), radius, selected["cells"])
        if footprints & occupied:
            raise ValueError("Ordinary initial actor footprints overlap")
        footprints.update(occupied)
    stage("selection")
    perimeter = cardinal_border_cells(selected["cells"]) if compact else frozenset()
    interior, borders = safe_interior(
        selected["cells"],
        selected["edges"],
        selected["placement"],
        perimeter,
        reserved_cells=footprints,
        placement_capacity=sum(
            max(12, len(team)) for team in selected["placement"].values()
        ),
    )
    placement = generate(
        interior,
        tuple(
            (start, end)
            for start, end in selected["edges"]
            if start in interior and end in interior
        ),
        seeds=selected["placement"],
        slots_per_team=12,
        avoid_cells=(),
        spread_teams=True,
        occupied_cells=footprints,
    )
    # Placement and both teams share the same native hazard-free component.
    # The complete arena remains available for movement and native effects.
    stage("placement")
    if surfaces is None:
        surfaces = native_qi_surfaces(map_id)
    stage("surface_catalog")
    indices = native_surface_indices(surfaces, selected["cells"])
    stage("surface_indices")
    result = arena(
        map_id,
        instance_id,
        sorted(selected["cells"]),
        placement,
        surface_indices=indices,
        border_cells=borders,
    )
    result.update(
        validated_cells=selected["cells"],
        valid_edges=selected["edges"],
        placement_cells=placement,
        native_qi_surface_provenance=native_qi_surface_provenance(map_id)
        if provenance is None
        else provenance,
        participant_positions=selected.get("participant_positions", []),
        native_border_cells=borders,
        native_border_policy="wakemu.compact-cardinal-perimeter-v1"
        if compact
        else None,
    )
    stage("wire")
    return result
