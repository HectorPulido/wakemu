"""Original Ranch building requests and scene deltas, separate from guild worlds."""
import struct


def _integer(value, lower, upper):
    if type(value) is not int or not lower <= value <= upper:
        raise ValueError("Invalid native Ranch building integer")
    return value


def decode_place(body):
    if not isinstance(body, bytes) or len(body) != 17:
        raise ValueError("Native12671 building placement requires17 bytes")
    reference, kind, view, x, y = struct.unpack(">iBiii", body)
    if reference <= 0 or kind not in (0, 1):
        raise ValueError("Invalid native building reference or view kind")
    return dict(building_ref=reference, view_kind=kind, view_value=view, x=x, y=y)


def decode_move(body):
    if not isinstance(body, bytes) or len(body) != 21:
        raise ValueError("Native12662 building movement requires21 bytes")
    uid, kind, view, x, y = struct.unpack(">qBiii", body)
    if uid <= 0 or kind not in (0, 1):
        raise ValueError("Invalid native building UID or view kind")
    return dict(uid=uid, view_kind=kind, view_value=view, x=x, y=y)


def decode_remove(body):
    if not isinstance(body, bytes) or len(body) != 8:
        raise ValueError("Native13480 building removal requires8 bytes")
    uid = struct.unpack(">q", body)[0]
    if uid <= 0:
        raise ValueError("Invalid native building removal UID")
    return uid


def building_record(row):
    """fBG.aqv/gK; preserve contained-item identity and quantity exactly."""
    keys = (
        "uid",
        "building_ref",
        "mode_id",
        "view_kind",
        "view_value",
        "x",
        "y",
        "contained_item_ref",
        "contained_quantity",
    )
    values = [row[key] for key in keys]
    _integer(values[0], 1, 2**63 - 1)
    for index, value in enumerate(values[1:], 1):
        _integer(
            value, 0 if index == 3 else -(2**31), 1 if index == 3 else 2**31 - 1
        )
    return struct.pack(">qiiBiiiii", *values)


def _world(world_id):
    return struct.pack(">q", _integer(world_id, -(2**63), 2**63 - 1))


def _scene_objects(scene_objects):
    if not isinstance(scene_objects, (list, tuple)) or len(scene_objects) > 127:
        raise ValueError("Invalid native changed-decoration collection")
    if any(not isinstance(row, bytes) or not row for row in scene_objects):
        raise ValueError("Changed scene_objects require actual fBM records")
    return struct.pack(">b", len(scene_objects)) + b"".join(scene_objects)


def placed(world_id, row, *, scene_objects):
    """czU12558 success; the caller supplies actual decoration changes."""
    return 12558, (
        _world(world_id)
        + b"\x01"
        + building_record(row)
        + struct.pack(">i", row["sector_id"])
        + _scene_objects(scene_objects)
    )


def moved(world_id, row, *, scene_objects):
    return 12530, (
        _world(world_id)
        + b"\x01"
        + building_record(row)
        + struct.pack(">i", row["sector_id"])
        + _scene_objects(scene_objects)
    )


def removed(world_id, uid, sector_id):
    """cAb12950 closes any detail panel for the actual retired building."""
    return 12950, _world(world_id) + struct.pack(">BqiB", 1, uid, sector_id, 1)


def rejected(opcode, world_id, *, uid=None):
    """Release the native pending operation without a successful mutation."""
    if opcode == 12671:
        return 12558, _world(world_id) + b"\x00"
    if opcode == 12662:
        return 12530, _world(world_id) + struct.pack(
            ">Bq", 0, _integer(uid, 1, 2**63 - 1)
        )
    if opcode == 13480:
        return 12950, _world(world_id) + b"\x00"
    raise ValueError("Unknown native Ranch building operation")
