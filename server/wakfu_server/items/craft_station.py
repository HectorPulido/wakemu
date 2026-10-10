"""Server-owned authority for static native CraftTable interaction.

CraftTable instances and environment objects come from separate native
exports. A request is accepted only when those records agree, the character
is in the static world instance, and its cell appears in the native-filtered
interaction cells for that table. Native bEG.dST derives the cells from the
direction mask, object orientation, and static map elevation. Client-supplied
position is never used.
"""
from wakfu_server import native_catalog as protocol_catalog

import json
from functools import lru_cache
from pathlib import Path

from wakfu_server.paths import DATA_ROOT


_FACING = {
    "NORTH",
    "NORTH_EAST",
    "EAST",
    "SOUTH_EAST",
    "SOUTH",
    "SOUTH_WEST",
    "WEST",
    "NORTH_WEST",
}
_DIRECTIONS = {
    "FRONT",
    "BACK",
    "LEFT",
    "RIGHT",
    "FRONT_LEFT",
    "FRONT_RIGHT",
    "BACK_LEFT",
    "BACK_RIGHT",
    "CENTER",
}


def load_interactions(path=DATA_ROOT / "craft-table-interaction-candidates.json"):
    document = protocol_catalog.load(Path(path))
    if not isinstance(document, dict):
        raise ValueError("Invalid native crafting interaction export")
    rows = document.get("instances")
    if (
        document.get("schema_version") != 1
        or document.get("row_count") != 330
        or document.get("candidate_count") != 566
        or document.get("vf_walkable_candidate_count") != 457
        or document.get("vf_filter_errors") != 0
        or not isinstance(document.get("native_filter_profile"), str)
        or not document["native_filter_profile"].startswith("Sm(3,0,2,true)")
        or not isinstance(rows, list)
        or len(rows) != 330
    ):
        raise ValueError("Incomplete native crafting interaction export")
    indexed = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Invalid native crafting interaction row")
        map_id, object_id, definition_id = (
            row.get("map_id"),
            row.get("object_id"),
            row.get("definition_id"),
        )
        identity = map_id, object_id
        if (
            type(map_id) is not int
            or map_id <= 0
            or type(object_id) is not int
            or object_id <= 0
            or type(definition_id) is not int
            or definition_id <= 0
            or identity in indexed
            or any(type(row.get(axis)) is not int for axis in ("x", "y", "z"))
            or type(row.get("interaction_mask")) is not int
            or not 0 < row["interaction_mask"] < 512
            or row.get("facing") not in _FACING
            or type(row.get("facing_angle")) is not int
            or not 0 <= row["facing_angle"] < 8
        ):
            raise ValueError("Invalid native crafting interaction identity or pose")
        candidates = row.get("raw_interaction_candidates")
        filtered = row.get("vf_walkable_interaction_cells")
        if not isinstance(candidates, list) or not candidates:
            raise ValueError("Missing native crafting interaction candidates")
        raw_xy = set()
        for candidate in candidates:
            if not isinstance(candidate, dict):
                raise ValueError("Invalid native crafting interaction candidate")
            bit = candidate.get("direction_bit")
            point = tuple(candidate.get(axis) for axis in ("x", "y", "z"))
            if (
                type(bit) is not int
                or bit <= 0
                or bit & row["interaction_mask"] != bit
                or any(type(value) is not int for value in point)
                or candidate.get("direction") not in _DIRECTIONS
            ):
                raise ValueError("Invalid native crafting interaction candidate")
            raw_xy.add(point[:2])
        if not isinstance(filtered, list):
            raise ValueError("Missing native-filtered crafting interaction cells")
        normalized = []
        seen = set()
        for candidate in filtered:
            if not isinstance(candidate, dict):
                raise ValueError("Invalid native-filtered interaction cell")
            point = tuple(candidate.get(axis) for axis in ("x", "y", "z"))
            if (
                any(type(value) is not int for value in point)
                or (point[0], point[1]) not in raw_xy
                or candidate.get("direction") not in _DIRECTIONS
                or type(candidate.get("direction_bit")) is not int
                or candidate["direction_bit"] <= 0
                or candidate["direction_bit"] & row["interaction_mask"]
                != candidate["direction_bit"]
            ):
                raise ValueError("Invalid native-filtered crafting interaction cell")
            if point not in seen:
                normalized.append(point)
                seen.add(point)
        indexed[identity] = {
            "definition_id": definition_id,
            "position": tuple(row[axis] for axis in ("x", "y", "z")),
            "interaction_mask": row["interaction_mask"],
            "facing": row["facing"],
            "cells": tuple(normalized),
            "raw_candidate_count": len(candidates),
        }
    if sum(row["raw_candidate_count"] for row in indexed.values()) != 566:
        raise ValueError("Native crafting candidate count mismatch")
    if sum(len(row["cells"]) for row in indexed.values()) != 457:
        raise ValueError("Native crafting filtered-cell count mismatch")
    return indexed


def resolve(character, table_id, catalog, *, objects, geometry):
    if (
        not isinstance(character, dict)
        or type(table_id) is not int
        or table_id <= 0
        or type(character.get("map_id")) is not int
        or character["map_id"] <= 0
        or type(character.get("instance_id")) is not int
        or character["instance_id"] != 0
    ):
        raise ValueError("Crafting requires a valid static-world actor")

    table = catalog.resolve_table(character["map_id"], table_id)
    if not isinstance(table, dict) or table.get("status") != "resolved":
        raise ValueError("Unknown native crafting table in current map")
    if (
        type(table.get("definition_id")) is not int
        or table["definition_id"] <= 0
        or type(table.get("profession_id")) is not int
        or table["profession_id"] <= 0
    ):
        raise ValueError("Invalid native crafting table definition")

    matches = [
        row
        for row in objects(character["map_id"])
        if row.get("id") == table_id and row.get("type") == "CraftTable"
    ]
    if len(matches) != 1:
        raise ValueError("Crafting table is not registered in the current world")
    world_object = matches[0]
    table_position = tuple(table.get(axis) for axis in ("x", "y", "z"))
    object_position = tuple(world_object.get(axis) for axis in ("x", "y", "z"))
    if table_position != object_position or any(
        type(value) not in (int, float) or int(value) != value
        for value in table_position
    ):
        raise ValueError("Crafting table world position is inconsistent")

    actor_position = tuple(character.get(axis) for axis in ("x", "y", "z"))
    if any(type(value) is not int for value in actor_position):
        raise ValueError("Invalid crafting actor position")
    native = native_interactions().get((character["map_id"], table_id))
    if (
        native is None
        or native["definition_id"] != table["definition_id"]
        or native["position"] != tuple(int(value) for value in table_position)
    ):
        raise ValueError("Missing or inconsistent native crafting interaction topology")
    cells = geometry(character["map_id"]).get("cells")
    if not isinstance(cells, list) and not isinstance(cells, tuple):
        raise ValueError("Missing native crafting map cells")
    walkable = {
        tuple(cell)
        for cell in cells
        if isinstance(cell, (list, tuple)) and len(cell) == 3
    }
    destination = tuple(int(value) for value in table_position)
    # The export has already applied VF.v with the same Sm(3,0,2,true) static
    # map profile used by the server's combat map export. Cross-check every
    # resolved native cell against that local static geometry before use.
    native_cells = set(native["cells"])
    if not native_cells.issubset(walkable):
        raise ValueError(
            "Native crafting interaction topology disagrees with map geometry"
        )
    if not native_cells:
        raise ValueError(
            "Crafting table is not reachable from the actor cell: "
            "native interaction candidates have no exact map surface"
        )
    if actor_position not in native_cells:
        raise ValueError("Crafting table is not reachable from the actor cell")

    return {
        "table_uid": table_id,
        "map_id": character["map_id"],
        "instance_id": 0,
        "definition_id": table["definition_id"],
        "profession_id": table["profession_id"],
        "in_range": True,
        "position": destination,
    }


@lru_cache(maxsize=1)
def _native_catalog():
    from .craft_catalog import load_catalog

    return load_catalog()


def resolve_current(character, table_id):
    """Resolve against installed native content used by the live dispatcher."""
    from wakfu_server import world_static
    from wakfu_server.combat_terrain import map_geometry

    if character.get("map_id") == 9 and character.get("instance_id", 0) > 0:
        from wakfu_server.haven_bag_furniture_catalog import furniture_templates

        return resolve_haven_bag(
            character, table_id, _native_catalog(), furniture_templates()
        )
    return resolve(
        character,
        table_id,
        _native_catalog(),
        objects=world_static.objects,
        geometry=map_geometry,
    )


def native_catalog():
    """Return the validated installed recipe and station catalog."""
    return _native_catalog()


@lru_cache(maxsize=1)
def native_interactions():
    """Return the complete native mask/orientation interaction export."""
    return load_interactions()


def resolve_haven_bag(character, table_id, catalog, templates):
    """Authorize native portable crafting against the current owned bag layout."""
    from wakfu_server.haven_bag_store import instance_id

    if (
        character.get("map_id") != 9
        or character.get("instance_id") != instance_id(character)
        or type(table_id) is not int
        or table_id <= 0
    ):
        raise ValueError("Crafting requires the owner's active haven-bag instance")
    config = character.get("haven_bag") or {}
    furniture = [
        row
        for row in config.get("furniture", [])
        if row.get("deployed") is True
        and table_id in (row.get("item_uid"), row.get("template_id"))
    ]
    if len(furniture) != 1:
        raise ValueError("Unknown portable crafting table in current map")
    item = furniture[0]
    template = templates.get(item["template_id"], {})
    definition_id = template.get("craft_definition_id")
    definition = catalog.definitions.get(definition_id)
    if not definition or not definition.get("profession_id"):
        raise ValueError("Unknown native portable crafting table definition")
    room = next(
        (row for row in config.get("rooms", []) if row["index"] == item["room"]), None
    )
    if room is None or not room.get("enabled") or room.get("primary_ref", -1) == -1:
        raise ValueError("Portable crafting table requires an active installed room")
    offsets = template.get("interaction_cells_by_direction", [])
    direction = item["direction"]
    if not 0 <= direction < len(offsets):
        raise ValueError("Missing native portable crafting interaction topology")
    actor_position = tuple(character.get(axis) for axis in ("x", "y", "z"))
    native_cells = {
        (item["x"] + dx, item["y"] + dy, item["z"] + dz)
        for dx, dy, dz in offsets[direction]
    }
    if actor_position not in native_cells:
        raise ValueError("Crafting table is not reachable from the actor cell")
    return dict(
        table_uid=table_id,
        map_id=9,
        instance_id=character["instance_id"],
        definition_id=definition_id,
        profession_id=definition["profession_id"],
        in_range=True,
        position=tuple(item[axis] for axis in ("x", "y", "z")),
        haven_bag=True,
    )
