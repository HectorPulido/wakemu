"""Native swimming surfaces, kept separate from world mount permissions."""
from wakfu_server import native_catalog as protocol_catalog
import json
from functools import lru_cache
from .paths import DATA_ROOT


@lru_cache(maxsize=32)
def cells(map_id):
    if type(map_id) is not int or map_id < 0:
        raise ValueError("Invalid swimming map identity")
    path = DATA_ROOT / "swimming-maps" / f"{map_id}.json"
    if not protocol_catalog.exists(path):
        raise ValueError("Native swimming topology is unavailable")
    data = protocol_catalog.load(path)
    validation = data.get("native_vf_validation", {})
    verified_empty = (
        validation.get("verified_empty") is True
        and type(validation.get("checked_chunks")) is int
        and validation["checked_chunks"] > 0
        and data.get("swimming_cells_xyz") == []
    )
    if (
        type(data.get("map_id")) is not int
        or data.get("map_id") != map_id
        or type(validation.get("mismatches")) is not int
        or validation.get("mismatches") != 0
        or type(validation.get("checked_surfaces")) is not int
        or validation.get("checked_surfaces") != data.get("surface_count")
        or type(data.get("surface_count")) is not int
        or data["surface_count"] < 0
        or (data["surface_count"] == 0 and not verified_empty)
    ):
        raise ValueError("Unverified native swimming topology")
    result = set()
    for position in data["swimming_cells_xyz"]:
        if (
            not isinstance(position, list)
            or len(position) != 3
            or any(type(value) is not int for value in position)
        ):
            raise ValueError("Invalid swimming surface position")
        result.add(tuple(position))
    return frozenset(result)


def at_position(character):
    position = tuple(character[key] for key in ("x", "y", "z"))
    if any(type(value) is not int for value in position):
        raise ValueError("Invalid authoritative swimming position")
    return position in cells(character["map_id"])
