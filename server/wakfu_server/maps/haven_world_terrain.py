"""Original Haven World patch terrain under an explicit internal template ID.

The positive ID is Wakemu's server geometry namespace; the official client sees
native world ID=-guildID and receives the original dynamic partition protocol.
Static geometry grants no access: durable guild assignment/session owns entry.
"""
from functools import lru_cache
from wakfu_server.haven_world_native import interior_geometry

TEMPLATE_MAP_ID = 2_000_000_000
PARTITIONS = ((0, -5, 0, 0, 0, 0),)
ENTRY = (4, -86, 0)


@lru_cache(maxsize=1)
def geometry():
    rows = interior_geometry()
    cells = {tuple(row[:3]) for row in rows if row[3] is False}
    if len(rows) != 324 or ENTRY not in cells:
        raise ValueError("Incomplete native Haven World base partition")
    edges = []
    for cell in sorted(cells):
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            target = (cell[0] + dx, cell[1] + dy, cell[2])
            if target in cells:
                edges.append([list(cell), list(target)])
    return dict(
        map_id=TEMPLATE_MAP_ID,
        cells=[list(c) for c in sorted(cells)],
        edges=edges,
        source="original cen.af partition(0,-5), patch0; explicit Wakemu namespace",
    )
