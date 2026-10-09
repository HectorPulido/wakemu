"""Exact native map/territory ownership for world x/y positions.

The installed bMh.dV(x,y) delegates to UL.an(Ve.qb(x),Ve.qc(y)); each Ve
coordinate is floor(coord / 18), including negative coordinates. The compact
catalog stores those native grid cells, not inferred rectangles or polygons.
"""
from wakfu_server import native_catalog as protocol_catalog
import json
from functools import lru_cache

from .paths import DATA_ROOT

GRID_SIZE = 18
_SOURCE = DATA_ROOT / "territory-map-cells.json"


@lru_cache(maxsize=1)
def _cells():
    catalog = protocol_catalog.load(_SOURCE)
    if catalog.get("schema_version") != 1 or catalog.get("grid_size") != GRID_SIZE:
        raise ValueError("Unsupported native territory cell catalog")
    maps = {}
    for map_row in catalog.get("maps", ()):
        map_id = map_row.get("map_id")
        if type(map_id) is not int or map_id in maps:
            raise ValueError("Invalid native territory map catalog")
        cells = {}
        for territory in map_row.get("regions", ()):
            region_id = territory.get("region_id")
            if type(region_id) is not int or region_id <= 0:
                raise ValueError("Invalid native territory identifier")
            for point in territory.get("cells", ()):
                if (
                    not isinstance(point, list)
                    or len(point) != 2
                    or any(type(value) is not int for value in point)
                ):
                    raise ValueError("Invalid native territory grid cell")
                cell = (point[0], point[1])
                if cell in cells:
                    raise ValueError("Overlapping native territory grid cells")
                cells[cell] = region_id
        maps[map_id] = cells
    return maps


def region_at(map_id, x, y):
    """Return the unique native territory at world x/y; never infer a default."""
    if any(type(value) is not int for value in (map_id, x, y)):
        raise ValueError("Invalid native territory position")
    grid = (x // GRID_SIZE, y // GRID_SIZE)
    region_id = _cells().get(map_id, {}).get(grid)
    if region_id is None:
        raise ValueError("Unknown native map territory at position")
    return region_id


def maps():
    """Expose immutable-size coverage counts for audit/health checks."""
    catalog = _cells()
    return {map_id: len(cells) for map_id, cells in catalog.items()}


def territories():
    """Return the exact map/region keys represented by the native cell export."""
    return tuple(
        sorted(
            (map_id, region_id)
            for map_id, cells in _cells().items()
            for region_id in set(cells.values())
        )
    )
