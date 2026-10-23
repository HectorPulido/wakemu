"""Original fBL neighbor masks and fBu minimal-superset view selection."""
from functools import lru_cache
from hashlib import sha256
import json
from pathlib import Path


_GROUP_SHA256 = "0e5c473765f87545979b713c7b1145e3b89432a13099fa56e276d2251479cecc"
# Original aAS.bWl: (dyI bit position, dyJ X offset, dyK Y offset).
_DIRECTIONS = (
    (0, 1, -1),
    (1, 1, 0),
    (2, 1, 1),
    (3, 0, 1),
    (4, -1, 1),
    (5, -1, 0),
    (6, -1, -1),
    (7, 0, -1),
)


@lru_cache(maxsize=1)
def _groups():
    raw = Path(__file__).with_name("native_ranch_adjacency_groups.json").read_bytes()
    if sha256(raw).hexdigest() != _GROUP_SHA256:
        raise ValueError("Native Ranch adjacency groups differ from their source")
    document = json.loads(raw)
    known = document["group_ids"]
    groups = document["building_groups"]
    if (
        not isinstance(known, list)
        or any(type(value) is not int for value in known)
        or not isinstance(groups, dict)
        or any(
            type(value) is not int or value not in known for value in groups.values()
        )
    ):
        raise ValueError("Invalid original Ranch adjacency registry")
    return {int(key): value for key, value in groups.items()}


def select_adjacent_key(observed_mask, keys):
    """fBu.abw: least populated superset, then the smallest numeric key."""
    if type(observed_mask) is not int or not 0 <= observed_mask <= 255:
        raise ValueError("Invalid native Ranch neighbor mask")
    candidates = []
    for key in keys:
        if type(key) is not int or not 0 <= key <= 255:
            raise ValueError("Invalid native Ranch adjacency view key")
        if observed_mask & ~key == 0:
            candidates.append(key)
    return min(candidates, key=lambda key: (key.bit_count(), key), default=None)


def recompute_adjacent_building_views(biome_id, rows):
    """Normalize current views from the complete owned post-mutation snapshot.

    Native fBV queries footprint occupancy, not just another building's anchor.
    Only view_kind/view_value can change; custody, mode and position stay owned
    by the placement transaction. Original missing-mask Optional leaves the
    current view unchanged.
    """
    from wakfu_server.haven_ranch_building_catalog import definitions, mode
    from wakfu_server.ranch_native_geometry import (
        building_footprint_cells,
        native_biome,
    )

    native_biome(biome_id)
    if not isinstance(rows, (list, tuple)):
        raise ValueError("Missing complete Ranch adjacency snapshot")
    groups, catalog = _groups(), definitions()
    copied, occupied, seen = [], {}, set()
    for source in rows:
        if not isinstance(source, dict):
            raise ValueError("Malformed native Ranch adjacency building")
        row = dict(source)
        uid, reference = row.get("uid"), row.get("building_ref")
        if type(uid) is not int or uid <= 0 or uid in seen or reference not in catalog:
            raise ValueError("Invalid native Ranch adjacency ownership")
        seen.add(uid)
        for point in building_footprint_cells(biome_id, [row]):
            if point in occupied:
                raise ValueError(
                    "Overlapping Ranch footprints have no unique adjacency owner"
                )
            occupied[point] = groups.get(reference)
        copied.append(row)
    for row in copied:
        group = groups.get(row["building_ref"])
        if group is None:
            continue
        definition = catalog[row["building_ref"]]
        if definition.get("epG") != group:
            raise ValueError("Native Ranch building group differs from its definition")
        observed = sum(
            1 << bit
            for bit, dx, dy in _DIRECTIONS
            if occupied.get((row["x"] + dx, row["y"] + dy)) == group
        )
        keys = [view["epL"] for view in mode(definition, row["mode_id"])["epQ"]]
        selected = select_adjacent_key(observed, keys)
        if selected is not None:
            row.update(view_kind=1, view_value=selected)
    return copied
