"""Pinned original fBm geometry for Ranch sector/account bootstrap.

This module exposes biome topology only. Static fBm.gxg building slots are
descriptors, not account-owned buildings, and are never copied into ownership.
"""
from functools import lru_cache
from hashlib import sha256
import json
from pathlib import Path


_CATALOG_SHA256 = "14083bf59e648102af3b3c8c64a3a731b6d470245390a7f9c6bbaeeb161b10dc"
_BIOME_ID = 1
_MAP_ID = 1440
_CHUNK_SIZE = 18
_FOOTPRINT_SHA256 = "f91ff213662da8a2b7c304b26cf3c949cd4240965e759deb6fead38a348a504c"
_PLACEMENT_TERRAIN_SHA256 = (
    "15e94ca9e41de2f0bb5faf5f72489d5a7dc7e360e3c7ec52e776b30bea19b4ca"
)


@lru_cache(maxsize=1)
def _topology():
    path = Path(__file__).with_name("native_ranch_biome_topology.json")
    raw = path.read_bytes()
    if sha256(raw).hexdigest() != _CATALOG_SHA256:
        raise ValueError("Native Ranch biome topology differs from its pinned source")
    data = json.loads(raw)
    if (
        data.get("schema_version") != 1
        or data.get("native_class") != "fBm"
        or data.get("native_biome_id") != _BIOME_ID
        or data.get("native_world_map_id") != _MAP_ID
        or data.get("provenance", {}).get("loader_class") != "bbE"
    ):
        raise ValueError("Unsupported native Ranch biome topology")
    areas = data.get("terrain_areas")
    if not isinstance(areas, list) or not areas:
        raise ValueError("Native Ranch biome has no fBm.gxf areas")
    ids, chunks = set(), set()
    for area in areas:
        if (
            not isinstance(area, dict)
            or type(area.get("id")) is not int
            or area["id"] < 0
            or area["id"] in ids
            or not isinstance(area.get("chunks"), list)
            or not area["chunks"]
        ):
            raise ValueError("Malformed native Ranch terrain area")
        ids.add(area["id"])
        for chunk in area["chunks"]:
            if (
                not isinstance(chunk, list)
                or len(chunk) != 2
                or any(type(v) is not int for v in chunk)
                or tuple(chunk) in chunks
            ):
                raise ValueError("Malformed or overlapping native Ranch chunks")
            chunks.add(tuple(chunk))
    slots = data.get("building_slots")
    if not isinstance(slots, list):
        raise ValueError("Native fBm.gxg building-slot catalog is missing")
    slot_ids = set()
    for slot in slots:
        if (
            not isinstance(slot, dict)
            or type(slot.get("id")) is not int
            or slot["id"] <= 0
            or slot["id"] in slot_ids
            or type(slot.get("x")) is not int
            or type(slot.get("y")) is not int
            or not isinstance(slot.get("cells"), list)
            or not slot["cells"]
        ):
            raise ValueError("Malformed native Ranch building slot")
        slot_ids.add(slot["id"])
    return data


@lru_cache(maxsize=1)
def _footprints():
    path = Path(__file__).with_name("native_ranch_building_footprints.json")
    raw = path.read_bytes()
    if sha256(raw).hexdigest() != _FOOTPRINT_SHA256:
        raise ValueError(
            "Native Ranch building footprints differ from their pinned source"
        )
    document = json.loads(raw)
    if (
        document.get("schema_version") != 1
        or document.get("native_classes") != ["bbH", "fBs", "fBu", "fBG", "fAz", "aBs"]
        or document.get("source_asset_sha256")
        != "83d32ce93198d3d71d95a97697662a7c945e1f5db5f2e5ad9f045375afff1fed"
        or document.get("definition_catalog_sha256")
        != "733982c0f8b5ac033756f4f2377aac766f1e6beba4a6620096cadf2b93a25c4b"
        or document.get("footprint_rule")
        != "original fBG.eAf() -> fAz.gQ(x,y) -> aBs.cK(x,y)"
    ):
        raise ValueError("Unsupported native Ranch footprint evidence")
    result = {}
    for row in document.get("footprints", ()):
        if not isinstance(row, dict):
            raise ValueError("Malformed native Ranch footprint row")
        ref, mode_id = row.get("building_ref"), row.get("mode_id")
        kind, selector = row.get("selection_kind"), row.get("selector_value")
        view_id = row.get("native_view_id")
        cells = row.get("cells")
        bounds = row.get("bounds")
        if (
            type(ref) is not int
            or ref <= 0
            or type(mode_id) is not int
            or mode_id < 0
            or kind not in (0, 1)
            or type(kind) is not int
            or type(selector) is not int
            or type(view_id) is not int
            or view_id <= 0
            or not isinstance(cells, list)
            or not cells
            or not isinstance(bounds, list)
            or len(bounds) != 4
            or any(type(value) is not int for value in bounds)
            or bounds[0] > bounds[1]
            or bounds[2] > bounds[3]
        ):
            raise ValueError("Malformed native Ranch footprint identity")
        offsets = []
        for cell in cells:
            if (
                not isinstance(cell, list)
                or len(cell) != 2
                or any(type(v) is not int for v in cell)
            ):
                raise ValueError("Malformed native Ranch footprint cell")
            offsets.append(tuple(cell))
        x_min, x_max, y_min, y_max = bounds
        if any(
            not (x_min <= dx <= x_max and y_min <= dy <= y_max) for dx, dy in offsets
        ):
            raise ValueError("Native Ranch footprint cells escape original bounds")
        key = (ref, mode_id, kind, selector)
        if key in result:
            raise ValueError("Duplicate native Ranch footprint selector")
        result[key] = {
            "view_id": view_id,
            "cells": tuple(offsets),
            "bounds": tuple(bounds),
        }
    return result


@lru_cache(maxsize=1)
def _placement_terrain():
    path = Path(__file__).with_name("native_ranch_placement_terrain.json")
    raw = path.read_bytes()
    if sha256(raw).hexdigest() != _PLACEMENT_TERRAIN_SHA256:
        raise ValueError(
            "Native Ranch placement terrain differs from its pinned source"
        )
    document = json.loads(raw)
    if (
        document.get("schema_version") != 1
        or document.get("map_id") != _MAP_ID
        or document.get("native_classes") != ["VC", "VB", "fBL"]
        or document.get("terrain_rule")
        != "fBL.a(VB,aBs): every bounds cell requires VB.aK && !VB.aJ"
        or document.get("chunks") != 28
    ):
        raise ValueError("Unsupported native Ranch placement terrain evidence")
    cells = {}
    for row in document.get("cells", ()):
        if (
            not isinstance(row, list)
            or len(row) != 3
            or any(type(value) is not int for value in row[:2])
            or type(row[2]) is not bool
        ):
            raise ValueError("Malformed native Ranch placement terrain cell")
        point = tuple(row[:2])
        if point in cells:
            raise ValueError("Duplicate native Ranch placement terrain cell")
        cells[point] = row[2]
    if len(cells) != 9072:
        raise ValueError("Incomplete native Ranch placement terrain plane")
    return cells


def native_biome(biome_id):
    if type(biome_id) is not int or biome_id != _BIOME_ID:
        raise ValueError("No installed Ranch biome topology for this biome")
    return _topology()


def initial_sectors(biome_id):
    """Return the actual fBm.gxf terrain-area IDs for this Ranch biome."""
    return tuple(sorted(area["id"] for area in native_biome(biome_id)["terrain_areas"]))


def sector_chunks(biome_id):
    """Return native fBm.gxf chunk membership keyed by sector/area ID."""
    return {
        area["id"]: frozenset(tuple(chunk) for chunk in area["chunks"])
        for area in native_biome(biome_id)["terrain_areas"]
    }


def sector_for_cell(biome_id, x, y):
    """Resolve fBm.gxf area using the native Ve.qb/qc 18-cell floor mapping."""
    if type(x) is not int or type(y) is not int:
        raise ValueError("Ranch terrain coordinates must be integers")
    chunk = (x // _CHUNK_SIZE, y // _CHUNK_SIZE)
    matches = [
        area_id
        for area_id, chunks in sector_chunks(biome_id).items()
        if chunk in chunks
    ]
    if len(matches) > 1:
        raise ValueError("Native Ranch terrain chunk has ambiguous area ownership")
    return matches[0] if matches else None


def building_slots(biome_id):
    """Return copies of static fBm.gxg slot descriptors, never owned instances."""
    return tuple(dict(row) for row in native_biome(biome_id)["building_slots"])


def validate_initial_area_policy(biome_id, configured_areas):
    """Require the furniture area policy to match original fBm.gxf exactly."""
    expected = sector_chunks(biome_id)
    actual = {}
    for row in configured_areas:
        if not isinstance(row, dict) or type(row.get("id")) is not int:
            raise ValueError("Malformed configured Ranch area")
        actual[row["id"]] = frozenset(tuple(chunk) for chunk in row.get("chunks", ()))
    if actual != expected:
        raise ValueError("Configured Ranch areas differ from original fBm.gxf")
    return tuple(sorted(expected))


def bootstrap_account_sectors(db, account_id, biome_id):
    """Idempotently create only the native initial area IDs for one account."""
    if type(account_id) is not int or account_id <= 0:
        raise ValueError("Invalid Ranch account sector owner")
    sectors = initial_sectors(biome_id)
    row = db.execute(
        "SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account_id,)
    ).fetchone()
    if row is None:
        raise ValueError("Unknown Ranch account")
    for sector_id in sectors:
        db.execute(
            "INSERT INTO account_ranch_sectors(account_id,biome_id,sector_id) "
            "VALUES(%s,%s,%s) ON CONFLICT(account_id,biome_id,sector_id) DO NOTHING",
            (account_id, biome_id, sector_id),
        )
    saved = tuple(
        row["sector_id"]
        for row in db.execute(
            "SELECT sector_id FROM account_ranch_sectors "
            "WHERE account_id=%s AND biome_id=%s ORDER BY sector_id",
            (account_id, biome_id),
        )
    )
    if saved != sectors:
        raise ValueError("Persisted Ranch sectors differ from native fBm.gxf")
    return sectors


def account_buildings_by_sector(db, account_id, biome_id):
    """Read and validate exact persisted fBG instances for fBE/fBV snapshots."""
    sectors = set(initial_sectors(biome_id))
    result = {sector_id: [] for sector_id in sorted(sectors)}
    rows = db.execute(
        "SELECT uid,account_id,biome_id,sector_id,building_ref,mode_id,view_kind,"
        "view_value,x,y,contained_item_ref,contained_quantity,revision "
        "FROM account_ranch_buildings WHERE account_id=%s AND biome_id=%s "
        "ORDER BY sector_id,uid",
        (account_id, biome_id),
    )
    from wakfu_server.haven_ranch_building_wire import building_record
    from wakfu_server.haven_ranch_building_catalog import definition, mode, view

    seen = set()
    for source in rows:
        row = dict(source)
        if row["sector_id"] not in result or row["uid"] in seen:
            raise ValueError("Persisted Ranch building has invalid sector or UID")
        if row["account_id"] != account_id or row["biome_id"] != biome_id:
            raise ValueError("Persisted Ranch building escaped its owner scope")
        building = definition(row["building_ref"])
        mode(building, row["mode_id"])
        view(building, row["mode_id"], row["view_kind"], row["view_value"])
        building_record(row)
        seen.add(row["uid"])
        result[row["sector_id"]].append(row)
    return {sector_id: tuple(values) for sector_id, values in result.items()}


def building_footprint_cells(biome_id, building_rows):
    """Expand persisted native fBG masks for collision with scene objects."""
    native_biome(biome_id)
    if not isinstance(building_rows, (list, tuple)):
        raise ValueError("Native Ranch building collision rows are unavailable")
    from wakfu_server.haven_ranch_building_catalog import definitions, view

    occupied = set()
    seen = set()
    for row in building_rows:
        if not isinstance(row, dict):
            raise ValueError("Malformed native Ranch building collision row")
        uid = row.get("uid")
        if type(uid) is not int or uid <= 0 or uid in seen:
            raise ValueError("Malformed native Ranch building collision identity")
        seen.add(uid)
        definition = definitions().get(row.get("building_ref"))
        if definition is None:
            raise ValueError("Persisted Ranch building has no pinned aMR definition")
        x, y = row.get("x"), row.get("y")
        if type(x) is not int or type(y) is not int:
            raise ValueError("Malformed persisted Ranch building position")
        native_view = view(
            definition, row.get("mode_id"), row.get("view_kind"), row.get("view_value")
        )
        key = (row["building_ref"], row["mode_id"], row["view_kind"], row["view_value"])
        shape = _footprints().get(key)
        if shape is None or shape["view_id"] != native_view["eki"]:
            raise ValueError("Original Ranch collision footprint is unavailable")
        occupied.update((x + dx, y + dy) for dx, dy in shape["cells"])
    return frozenset(occupied)


def deployed_creature_cells(db, account_id, biome_id):
    """Return original fBQ anchor cells for currently deployed account creatures.

    Original fBV.hc checks each fBQ's exact x/y cell; it does not expand model
    size, scale, or nearby cells. Keep occupancy tied to the persisted owner,
    biome, and sector rather than the visiting character.
    """
    native_biome(biome_id)
    if type(account_id) is not int or account_id <= 0:
        raise ValueError("Invalid Ranch creature occupancy owner")
    from wakfu_server import haven_ranch_herd

    creatures_by_sector = haven_ranch_herd.sector_records(db, account_id, biome_id)
    valid_sectors = set(initial_sectors(biome_id))
    paddock_uids_by_sector = {}
    for paddock in haven_ranch_herd.paddocks(db, account_id, biome_id):
        sector_id = paddock.get("sector_id")
        uid = paddock.get("uid")
        if type(sector_id) is not int or type(uid) is not int or uid <= 0:
            raise ValueError("Malformed native Ranch paddock identity")
        paddock_uids_by_sector.setdefault(sector_id, set()).add(uid)
    seen = set()
    cells = set()
    for sector_id, creatures in creatures_by_sector.items():
        if type(sector_id) is not int or sector_id not in valid_sectors:
            raise ValueError("Invalid native Ranch creature sector")
        paddock_uids = paddock_uids_by_sector.get(sector_id, set())
        for creature in creatures:
            if not isinstance(creature, dict):
                raise ValueError("Malformed native Ranch creature occupancy record")
            uid = creature.get("uid")
            paddock_uid = creature.get("native_tJU")
            x, y = creature.get("x"), creature.get("y")
            if (
                type(uid) is not int
                or uid <= 0
                or uid in seen
                or creature.get("native_tJT") is not False
                or creature.get("native_eqf") != biome_id
                or type(paddock_uid) is not int
                or paddock_uid not in paddock_uids
                or type(x) is not int
                or type(y) is not int
                or sector_for_cell(biome_id, x, y) != sector_id
            ):
                raise ValueError("Invalid native Ranch creature occupancy identity")
            seen.add(uid)
            cells.add((x, y))
    return frozenset(cells)


def validate_building_placement(
    definition,
    mode_id,
    view_kind,
    view_value,
    x,
    y,
    *,
    biome_id,
    existing_buildings,
    occupied_cells,
):
    """Use original fBm, fBG/aBs, fBL and VB data to validate placement."""
    if not isinstance(definition, dict):
        raise ValueError("Missing original aMR Ranch building definition")
    if type(x) is not int or type(y) is not int:
        raise ValueError("Ranch building coordinates must be integers")
    from wakfu_server.haven_ranch_building_catalog import definitions, mode, view

    reference = definition.get("p")
    if type(reference) is not int or definitions().get(reference) != definition:
        raise ValueError("Ranch building definition is not from the pinned aMR catalog")

    def selected_shape(building, row_mode, row_kind, row_value):
        selected_view = view(building, row_mode, row_kind, row_value)
        key = (building["p"], row_mode, row_kind, row_value)
        shape = _footprints().get(key)
        if shape is None or shape["view_id"] != selected_view["eki"]:
            raise ValueError(
                "Original Ranch collision footprint is unavailable for this view"
            )
        return shape

    def absolute_cells(building, row_mode, row_kind, row_value, origin_x, origin_y):
        shape = selected_shape(building, row_mode, row_kind, row_value)
        return frozenset((origin_x + dx, origin_y + dy) for dx, dy in shape["cells"])

    mode(definition, mode_id)
    sector_id = sector_for_cell(biome_id, x, y)
    if sector_id is None:
        raise ValueError("Ranch building anchor is outside native fBm.gxf sectors")
    if not isinstance(existing_buildings, (list, tuple)):
        raise ValueError("Ranch building collision set is unavailable")
    if not isinstance(occupied_cells, (list, tuple, set, frozenset)):
        raise ValueError("Native Ranch decoration/resource occupancy is unavailable")
    shape = selected_shape(definition, mode_id, view_kind, view_value)
    candidate = frozenset((x + dx, y + dy) for dx, dy in shape["cells"])
    if not candidate or any(
        sector_for_cell(biome_id, px, py) != sector_id for px, py in candidate
    ):
        raise ValueError("Native Ranch building footprint leaves its fBm.gxf sector")
    terrain = _placement_terrain()
    x_min, x_max, y_min, y_max = shape.get("bounds", ())
    if any(type(value) is not int for value in (x_min, x_max, y_min, y_max)):
        raise ValueError("Native Ranch footprint has no original placement bounds")
    for terrain_x in range(x + x_min, x + x_max + 1):
        for terrain_y in range(y + y_min, y + y_max + 1):
            blocked = terrain.get((terrain_x, terrain_y))
            if blocked is None:
                raise ValueError("Native Ranch footprint leaves original VB bounds")
            if blocked:
                raise ValueError("Native VB terrain blocks the building footprint")
    seen = set()
    occupied = set()
    for cell in occupied_cells:
        if (
            not isinstance(cell, (list, tuple))
            or len(cell) != 2
            or any(type(value) is not int for value in cell)
        ):
            raise ValueError("Malformed Ranch scene-object occupancy point")
        occupied.add(tuple(cell))
    for row in existing_buildings:
        if not isinstance(row, dict):
            raise ValueError("Malformed native Ranch building collision row")
        uid = row.get("uid")
        if type(uid) is not int or uid <= 0 or uid in seen:
            raise ValueError("Malformed native Ranch building collision set")
        seen.add(uid)
        row_x, row_y = row.get("x"), row.get("y")
        if type(row_x) is not int or type(row_y) is not int:
            raise ValueError("Malformed persisted Ranch building position")
        existing_definition = definitions().get(row.get("building_ref"))
        if existing_definition is None:
            raise ValueError("Persisted Ranch building has no pinned aMR definition")
        other = absolute_cells(
            existing_definition,
            row.get("mode_id"),
            row.get("view_kind"),
            row.get("view_value"),
            row_x,
            row_y,
        )
        if row.get("sector_id") != sector_for_cell(biome_id, row_x, row_y):
            raise ValueError(
                "Persisted Ranch building sector differs from native fBm.gxf"
            )
        if any(
            sector_for_cell(biome_id, px, py) != row["sector_id"] for px, py in other
        ):
            raise ValueError("Persisted Ranch building crosses native fBm.gxf sectors")
        occupied.update(other)
    if candidate & occupied:
        raise ValueError("Native Ranch building footprint overlaps an existing object")
    return {"sector_id": sector_id, "footprint_cells": tuple(sorted(candidate))}


def changed_scene_object_records(biome_id, before, after):
    """Require the exact native fBM child producer for changed building views."""
    native_biome(biome_id)
    if not isinstance(before, (list, tuple)) or not isinstance(after, (list, tuple)):
        raise ValueError("Ranch scene-object snapshots are malformed")
    from wakfu_server.haven_ranch_building_catalog import definitions
    from wakfu_server import haven_ranch_building_children

    before_by_uid = {row.get("uid"): row for row in before if isinstance(row, dict)}
    after_by_uid = {row.get("uid"): row for row in after if isinstance(row, dict)}
    if len(before_by_uid) != len(before) or len(after_by_uid) != len(after):
        raise ValueError("Ranch scene-object snapshots contain malformed rows")
    changed = {
        uid
        for uid in set(before_by_uid) | set(after_by_uid)
        if before_by_uid.get(uid) != after_by_uid.get(uid)
    }
    for uid in changed:
        # Native ceK removal drops attached scene objects automatically, but
        # placement or mutation needs the selected view's actual fBM producer.
        after_row = after_by_uid.get(uid)
        if after_row is None:
            continue
        rows_to_validate = [after_row]
        before_row = before_by_uid.get(uid)
        if before_row is not None:
            rows_to_validate.append(before_row)
        for row in rows_to_validate:
            building = definitions().get(row.get("building_ref"))
            if building is None:
                raise ValueError("Changed Ranch building has no pinned aMR definition")
            haven_ranch_building_children.validate_building_children(
                building,
                row.get("mode_id"),
                row.get("view_kind"),
                row.get("view_value"),
            )
    return ()


def recompute_adjacent_building_views(biome_id, building_rows):
    """Reproduce the native fBL view update after placement, move, or removal.

    The Ranch operation layer applies this to the complete account-owned
    population after each mutation and persists only the changed view fields.
    Adjacency selection itself belongs to the independently pinned native
    fBL/fBu implementation.
    """
    native_biome(biome_id)
    if not isinstance(building_rows, (list, tuple)):
        raise ValueError("Native Ranch adjacency rows are unavailable")
    from wakfu_server import ranch_native_adjacency

    result = ranch_native_adjacency.recompute_adjacent_building_views(
        biome_id, tuple(dict(row) for row in building_rows)
    )
    if not isinstance(result, (list, tuple)) or len(result) != len(building_rows):
        raise ValueError("Native Ranch adjacency returned an incomplete population")
    before_by_uid = {}
    after_by_uid = {}
    from wakfu_server.haven_ranch_building_catalog import definition, mode, view
    from wakfu_server.haven_ranch_building_children import validate_building_children

    for rows, target in ((building_rows, before_by_uid), (result, after_by_uid)):
        for source in rows:
            if not isinstance(source, dict):
                raise ValueError("Malformed native Ranch adjacency row")
            row = dict(source)
            uid = row.get("uid")
            if type(uid) is not int or uid <= 0 or uid in target:
                raise ValueError("Malformed native Ranch adjacency identity")
            building = definition(row.get("building_ref"))
            mode(building, row.get("mode_id"))
            view(
                building,
                row.get("mode_id"),
                row.get("view_kind"),
                row.get("view_value"),
            )
            target[uid] = row
    if before_by_uid.keys() != after_by_uid.keys():
        raise ValueError("Native adjacency changed the owned building population")
    for uid, before in before_by_uid.items():
        after = after_by_uid[uid]
        if set(after) != set(before) or any(
            after[key] != value
            for key, value in before.items()
            if key not in {"view_kind", "view_value"}
        ):
            raise ValueError("Native adjacency changed unrelated building state")
        if (after["view_kind"], after["view_value"]) != (
            before["view_kind"],
            before["view_value"],
        ):
            building = definition(after["building_ref"])
            view(building, after["mode_id"], after["view_kind"], after["view_value"])
            validate_building_children(
                building, after["mode_id"], after["view_kind"], after["view_value"]
            )
    return tuple(after_by_uid[uid] for uid in before_by_uid)
