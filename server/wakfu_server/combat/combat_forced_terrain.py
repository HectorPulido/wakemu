"""Offline native faz.B/Sm first-surface priority, separate from walking edges."""
from wakfu_server import native_catalog as protocol_catalog
from collections.abc import Mapping
import json
from functools import lru_cache
from types import MappingProxyType
from wakfu_server.paths import DATA_ROOT


class HeightPolicy(Mapping):
    """Select masks lazily: multiple actor heights share one immutable index."""

    def __init__(self, index, height):
        self._index = index
        self._bit = 1 << (height - 1)

    def __getitem__(self, key):
        for mask, destination in self._index[key]:
            if mask & self._bit:
                return destination
        raise KeyError(key)

    def __iter__(self):
        return iter(self._index)

    def __len__(self):
        return len(self._index)


@lru_cache(maxsize=4)
def compact_index(map_id, radius, jump):
    if (radius, jump) == (0, 4):
        from wakfu_server.prepared_geometry import published_artifact

        prepared = published_artifact(map_id)
        if prepared is not None and prepared.forced_index is not None:
            return prepared.forced_index
    path = DATA_ROOT / "forced-transitions" / f"{map_id}.json"
    data = protocol_catalog.load(path)
    return prepare_compact_index(data, map_id, radius, jump)


def prepare_compact_index(data, map_id, radius, jump):
    """Validate the complete native export for runtime or offline preparation."""
    if (
        data.get("schema_version"),
        data.get("map_id"),
        data.get("radius"),
        data.get("jump"),
        data.get("heights"),
    ) != (1, map_id, radius, jump, [1, 25]):
        raise ValueError("Native compact forced terrain export policy mismatch")
    full_mask = (1 << 25) - 1
    index = {}
    for row in data["rows"]:
        if len(row) != 6 or any(type(n) is not int for n in row[:5]):
            raise ValueError("Malformed native compact forced terrain query")
        x, y, z, dx, dy, variants = row
        if abs(dx) + abs(dy) != 1:
            raise ValueError("Non-cardinal native compact forced terrain query")
        key = ((x, y, z), (x + dx, y + dy))
        if key in index:
            raise ValueError("Duplicate native compact forced terrain query")
        covered = 0
        choices = []
        for mask, destination_z in variants:
            if (
                type(mask) is not int
                or mask <= 0
                or mask & ~full_mask
                or covered & mask
                or destination_z is not None
                and type(destination_z) is not int
            ):
                raise ValueError("Invalid or overlapping native forced height mask")
            covered |= mask
            choices.append(
                (
                    mask,
                    None if destination_z is None else (x + dx, y + dy, destination_z),
                )
            )
        if covered != full_mask:
            raise ValueError("Incomplete native forced height coverage")
        index[key] = tuple(choices)
    return MappingProxyType(index)


@lru_cache(maxsize=8)
def transitions(map_id, height, radius=0, jump=4):
    if any(type(v) is not int for v in (map_id, height, radius, jump)):
        raise ValueError("Native forced terrain policy requires exact integer metadata")
    directory = DATA_ROOT / "forced-transitions"
    if protocol_catalog.exists(directory / f"{map_id}.json"):
        if not 1 <= height <= 25:
            raise ValueError("Missing native forced terrain policy for physical height")
        return HeightPolicy(compact_index(map_id, radius, jump), height)
    path = directory / f"{map_id}-h{height}-r{radius}-j{jump}.json"
    if not protocol_catalog.exists(path):
        raise ValueError(
            "Missing native forced terrain policy for map/height/radius/jump"
        )
    data = protocol_catalog.load(path)
    if tuple(data.get(k) for k in ("map_id", "height", "radius", "jump")) != (
        map_id,
        height,
        radius,
        jump,
    ):
        raise ValueError("Native forced terrain export policy mismatch")
    return {
        (tuple(src), tuple(xy)): None if dst is None else tuple(dst)
        for src, xy, dst in data["rows"]
    }


def next_surface(map_id, height, source, xy, *, radius=0, jump=4):
    """None is an explicitly exported collision; absent source is unknown."""
    key = (tuple(source), tuple(xy))
    table = transitions(map_id, height, radius, jump)
    if key not in table:
        raise ValueError("Native forced terrain source/query is not exported")
    return table[key]


def prewarm_map(map_id):
    """Validate/load available native geometry before the first displacement.

    Absent exports remain unsupported; warming must not invent a terrain policy
    or prevent a fight that never needs forced movement.
    """
    if type(map_id) is not int:
        raise ValueError("Native map ID requires an exact integer")
    if not protocol_catalog.exists(DATA_ROOT / "forced-transitions" / f"{map_id}.json"):
        return False
    compact_index(map_id, 0, 4)
    return True
