"""Bounded fight terrain selected from installed-client map exports."""
from wakfu_server import native_catalog as protocol_catalog
import json
import os
import random
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
from .combat_geometry import published_geometry
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
):
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
    configured_radius = int(os.environ.get("WAKFU_COMBAT_ARENA_RADIUS", "89"))
    if compact:
        # Callers may supply a stable seed for retries; new fights vary by default.
        formation = random.Random(variation_seed)
        if minimum_dimensions is None:
            minimum_width = formation.randint(5, 7)
            minimum_height = formation.randint(5, 7)
        else:
            minimum_width, minimum_height = minimum_dimensions
        selected = compact_encounter(
            geometry,
            player_position,
            members,
            minimum_cells=minimum_width * minimum_height,
            minimum_dimensions=(minimum_width, minimum_height),
            spread_opponents=relocate_monsters,
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
    perimeter = cardinal_border_cells(selected["cells"]) if compact else frozenset()
    placement = generate(
        selected["cells"],
        selected["edges"],
        seeds=selected["placement"],
        slots_per_team=12,
        avoid_cells=perimeter,
        spread_teams=True,
    )
    # Native walls and narrow components may not offer interior formation
    # capacity. Preserve their collision rules, but never draw a combat border
    # beneath an actor seed or any selectable placement cell.
    borders = perimeter - placement[0] - placement[1]
    indices = native_surface_indices(
        native_qi_surfaces(map_id) if surfaces is None else surfaces,
        selected["cells"],
    )
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
    return result
