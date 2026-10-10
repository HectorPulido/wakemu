"""Bounded fight terrain selected from installed-client map exports."""
from wakfu_server import native_catalog as protocol_catalog
import json
import os
import random
from functools import lru_cache
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
    variation_seed=None
):
    members = monster_position
    if (
        isinstance(members, (tuple, list))
        and len(members) == 3
        and all(type(v) is int for v in members)
    ):
        members = [members]
    configured_radius = int(os.environ.get("WAKFU_COMBAT_ARENA_RADIUS", "89"))
    if relocate_monsters:
        # Callers may supply a stable seed for retries; new fights vary by default.
        formation = random.Random(variation_seed)
        minimum_width = formation.randint(5, 7)
        minimum_height = formation.randint(5, 7)
        selected = compact_encounter(
            published_geometry(map_id),
            player_position,
            members,
            minimum_cells=minimum_width * minimum_height,
            minimum_dimensions=(minimum_width, minimum_height),
        )
    else:
        selected = bounded_arena(
            published_geometry(map_id),
            player_position,
            members,
            radius=configured_radius,
        )
    perimeter = (
        cardinal_border_cells(selected["cells"]) if relocate_monsters else frozenset()
    )
    placement = generate(
        selected["cells"],
        selected["edges"],
        seeds=selected["placement"],
        slots_per_team=12,
        avoid_cells=perimeter,
    )
    # Native walls and narrow components may not offer interior formation
    # capacity. Preserve their collision rules, but never draw a combat border
    # beneath an actor seed or any selectable placement cell.
    borders = perimeter - placement[0] - placement[1]
    indices = native_surface_indices(native_qi_surfaces(map_id), selected["cells"])
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
        native_qi_surface_provenance=native_qi_surface_provenance(map_id),
        participant_positions=selected.get("participant_positions", []),
        native_border_cells=borders,
        native_border_policy="wakemu.compact-cardinal-perimeter-v1"
        if relocate_monsters
        else None,
    )
    return result
