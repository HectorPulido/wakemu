"""Bounded fight terrain selected from installed-client map exports."""
import gzip
import json
import os
from functools import lru_cache
from .paths import DATA_ROOT
from .combat_wire import arena
from .combat_arena_selection import bounded_arena
from .combat_placement_cells import generate

SOURCE = DATA_ROOT / "amakna-test-arena.json"


@lru_cache(maxsize=16)
def map_geometry(map_id):
    if type(map_id) is not int or map_id <= 0:
        raise ValueError("Invalid combat map identity")
    directory = DATA_ROOT / "combat-maps"
    for suffix in (".json.gz", ".json"):
        path = directory / (str(map_id) + suffix)
        if path.is_file():
            opener = gzip.open if suffix.endswith(".gz") else open
            with opener(path, "rt", encoding="utf8") as source:
                data = json.load(source)
            if data.get("map_id") != map_id:
                raise ValueError("Combat map export identity mismatch")
            return data
    # Transitional fixtures are discovered by their own metadata, never by
    # mapping a requested destination to a different map's geometry.
    for path in DATA_ROOT.glob("*-test-arena.json"):
        data = json.loads(path.read_text())
        if data.get("map_id") == map_id:
            return data
    raise ValueError("No installed-client geometry export for this map")


def local_arena(map_id, instance_id, player_position, monster_position):
    members = monster_position
    if (
        isinstance(members, (tuple, list))
        and len(members) == 3
        and all(type(v) is int for v in members)
    ):
        members = [members]
    radius = int(os.environ.get("WAKFU_COMBAT_ARENA_RADIUS", "89"))
    selected = bounded_arena(
        map_geometry(map_id), player_position, members, radius=radius
    )
    placement = generate(
        selected["cells"],
        selected["edges"],
        seeds={0: [tuple(player_position)], 1: [tuple(p) for p in members]},
        slots_per_team=12,
    )
    result = arena(map_id, instance_id, sorted(selected["cells"]), placement)
    result.update(
        validated_cells=selected["cells"],
        valid_edges=selected["edges"],
        placement_cells=placement,
    )
    return result
