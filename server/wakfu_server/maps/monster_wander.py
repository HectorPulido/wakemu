"""World SQL policy adapter and native spatial proposal checks."""

import math

from wakfu_server.spatial_native import get_spatial
from wakfu_server.spatial_geometry import (
    NativeNeighbors,
    actor_position,
    member_rows,
    group_rows,
    edge_index,
)


def point(actor):
    return tuple(get_spatial().call("geometry.point", actor=actor_position(actor)))


def policy(store):
    with store.connection() as db:
        row = db.execute(
            "SELECT value FROM settings WHERE name='monster_wander'"
        ).fetchone()
    value = row["value"] if row is not None else None
    if not isinstance(value, dict) or set(value) != {
        "interval_seconds",
        "move_probability",
        "min_steps",
        "max_steps",
        "radius",
    }:
        raise ValueError("Invalid monster wander policy")
    for key in ("interval_seconds", "move_probability"):
        if type(value[key]) not in (int, float) or not math.isfinite(value[key]):
            raise ValueError("Invalid monster wander timing or probability")
    if (
        not 0 < value["interval_seconds"] <= 3600
        or not 0 <= value["move_probability"] <= 1
    ):
        raise ValueError("Invalid monster wander timing or probability")
    if (
        any(type(value[key]) is not int for key in ("min_steps", "max_steps", "radius"))
        or not 1 <= value["min_steps"] <= value["max_steps"] <= 255
        or not 1 <= value["radius"] <= 1000
    ):
        raise ValueError("Invalid monster wander distance")
    return value


DISPERSION_RADIUS = 12


def group_neighbor_index(groups):
    return NativeNeighbors(groups)


def nearest_group(origin, buckets, *, exclude_id=None):
    result = buckets.index.call(
        "geometry.nearest_group", origin=origin, exclude_id=exclude_id
    )
    return None if result is None else tuple(result)


def separating_movement(expected, moved, othergroups):
    return get_spatial().call(
        "geometry.separating_movement",
        expected=member_rows(expected),
        moved=member_rows(moved),
        groups=group_rows(othergroups),
    )


def _occupancy(operation, members, players, other_groups):
    return get_spatial().call(
        operation,
        members=member_rows(members),
        players=[actor_position(player) for player in players],
        groups=group_rows(other_groups),
    )


def _external_cells(members, players, other_groups):
    return set(
        map(
            tuple, _occupancy("geometry.external_cells", members, players, other_groups)
        )
    )


def _overlap_count(members, players, other_groups):
    return _occupancy("geometry.overlap_count", members, players, other_groups)


def has_overlap(members, players, other_groups):
    return _occupancy("geometry.has_overlap", members, players, other_groups)


def clear_destination(members, players, other_groups):
    return _occupancy("geometry.clear_destination", members, players, other_groups)


def overlap_escape_valid(expected, moved, players, othergroups):
    return get_spatial().call(
        "geometry.overlap_escape_valid",
        expected=member_rows(expected),
        moved=member_rows(moved),
        players=[actor_position(player) for player in players],
        groups=group_rows(othergroups),
    )
