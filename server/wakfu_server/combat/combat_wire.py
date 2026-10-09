"""Current fight bootstrap envelopes, independently built from owned state.

Nested blobs are explicit inputs: decoding an envelope is not proof that its
actor/effect data is suitable for a live fight. Never reuse foreign actor blobs.
"""
import struct
from protocol_codec import Reader


def _blob(data, fmt):
    if not isinstance(data, bytes):
        raise ValueError("Fight section must be bytes")
    limit = 32767 if fmt == "h" else 2147483647
    if len(data) > limit:
        raise ValueError("Fight section exceeds signed Java length")
    return struct.pack(">" + fmt, len(data)) + data


def _read_blob(reader, fmt):
    return reader.take(reader.number(fmt))


def actor_state(opcode, fight_id, actor_id, state):
    """13912/cuV uses i32 size; 12873/cuU uses signed i16 size."""
    if opcode not in (13912, 12873):
        raise ValueError("Unsupported fight actor envelope")
    return struct.pack(">iq", fight_id, actor_id) + _blob(
        state, "i" if opcode == 13912 else "h"
    )


def decode_actor_state(opcode, body):
    if opcode not in (13912, 12873):
        raise ValueError("Unsupported fight actor envelope")
    r = Reader(body)
    value = dict(
        fight_id=r.number("i"),
        actor_id=r.number("q"),
        state=_read_blob(r, "i" if opcode == 13912 else "h"),
    )
    r.finish()
    return value


def bootstrap(value):
    """Encode cvb12847, preserving neutral field names until handlers establish semantics."""
    participants = value["participants"]
    if len(participants) > 127:
        raise ValueError("Too many fight participants")
    compact = bool(value.get("compact", False))
    out = struct.pack(
        ">ibqqq",
        value["fight_id"],
        value["kind"],
        value["bqh"],
        value["myo"],
        value["myp"],
    )
    out += _blob(value["myD"], "i") + _blob(value["myG"], "h")
    out += struct.pack(">qqBB", value["myI"], value["myJ"], compact, len(participants))
    for actor in participants:
        out += struct.pack(
            ">qbbb", actor["actor_id"], actor["myB"], actor["myn"], actor["myC"]
        )
        if not compact:
            out += _blob(actor["myE"], "h") + _blob(actor["myF"], "h")
    for key in ("myH", "myM", "myN"):
        items = value.get(key, [])
        if len(items) > 127:
            raise ValueError("Fight list exceeds signed byte count")
        out += struct.pack(">b", len(items))
        out += b"".join(
            struct.pack(">bq", *item) if key == "myH" else struct.pack(">b", item)
            for item in items
        )
    sections = value.get("myK", [])
    out += struct.pack(">i", len(sections)) + b"".join(
        _blob(item, "i") for item in sections
    )
    return out


def decode_bootstrap(body):
    r = Reader(body)
    value = {
        key: r.number(fmt)
        for key, fmt in [
            ("fight_id", "i"),
            ("kind", "b"),
            ("bqh", "q"),
            ("myo", "q"),
            ("myp", "q"),
        ]
    }
    value.update(
        myD=_read_blob(r, "i"),
        myG=_read_blob(r, "h"),
        myI=r.number("q"),
        myJ=r.number("q"),
    )
    compact = r.number("B")
    if compact not in (0, 1):
        raise ValueError("Invalid compact flag")
    value["compact"] = bool(compact)
    count = r.number("b")
    if count < 0:
        raise ValueError("Negative participant count")
    value["participants"] = []
    for _ in range(count):
        actor = {
            key: r.number(fmt)
            for key, fmt in [
                ("actor_id", "q"),
                ("myB", "b"),
                ("myn", "b"),
                ("myC", "b"),
            ]
        }
        if not compact:
            actor.update(myE=_read_blob(r, "h"), myF=_read_blob(r, "h"))
        value["participants"].append(actor)
    for key in ("myH", "myM", "myN"):
        count = r.number("b")
        if count < 0:
            raise ValueError("Negative fight list count")
        value[key] = [
            (r.number("b"), r.number("q")) if key == "myH" else r.number("b")
            for _ in range(count)
        ]
    count = r.number("i")
    if count < 0 or count > len(body) // 4:
        raise ValueError("Invalid fight section count")
    value["myK"] = [_read_blob(r, "i") for _ in range(count)]
    r.finish()
    return value


def topology(value):
    """fct/QI arena using installed client map cells (no inline fcy override).

    Cell masks cover width*height cells. Placement-team metadata and movement flags
    remain explicit inputs; this does not invent walkable cells in asset geometry.
    """
    width, height = value["width"], value["height"]
    masks = value["cell_masks"]
    if width < 1 or height < 1 or width * height != len(masks) or len(masks) > 32767:
        raise ValueError("Invalid arena dimensions or cell mask count")
    flags = value.get("cell_flags")
    if flags is not None and (not isinstance(flags, bytes) or len(flags) != len(masks)):
        raise ValueError("Invalid arena cell flag count")
    teams = value.get("team_values", [])
    if len(teams) > 127:
        raise ValueError("Too many arena team entries")
    out = struct.pack(
        ">hhiiiihhh",
        value["map_id"],
        value["instance_id"],
        value["x"],
        value["y"],
        width,
        height,
        value["min_z"],
        value["max_z"],
        len(masks),
    )
    out += struct.pack(">" + "h" * len(masks), *masks)
    out += bytes([flags is not None]) + (flags or b"")
    out += struct.pack(
        ">Bbbb", 0, value.get("flag_R", 0), value.get("flag_S", 0), len(teams)
    )
    out += b"".join(struct.pack(">bi", *team) for team in teams)
    return out


def decode_topology(body):
    r = Reader(body)
    value = {
        key: r.number(fmt)
        for key, fmt in [
            ("map_id", "h"),
            ("instance_id", "h"),
            ("x", "i"),
            ("y", "i"),
            ("width", "i"),
            ("height", "i"),
            ("min_z", "h"),
            ("max_z", "h"),
        ]
    }
    count = r.number("h")
    if (
        count < 1
        or value["width"] < 1
        or value["height"] < 1
        or count != value["width"] * value["height"]
    ):
        raise ValueError("Invalid arena dimensions or cell mask count")
    value["cell_masks"] = [r.number("h") for _ in range(count)]
    present = r.number("B")
    if present not in (0, 1):
        raise ValueError("Invalid arena cell flag presence")
    value["cell_flags"] = r.take(count) if present else None
    if r.number("B") != 0:
        raise ValueError("Inline fcy terrain overrides are not implemented")
    value.update(flag_R=r.number("b"), flag_S=r.number("b"))
    count = r.number("b")
    if count < 0:
        raise ValueError("Negative arena team count")
    value["team_values"] = [(r.number("b"), r.number("i")) for _ in range(count)]
    r.finish()
    return value


def arena(
    map_id,
    instance_id,
    cells,
    placement,
    *,
    obstacle_values=None,
    surface_indices=None,
    border_cells=()
):
    """Build a bounded arena from prevalidated (x,y,z) client-map cells.

    Caller must obtain cells from installed map topology. Unselected rectangle
    cells receive the QI blocked bit0x100. Only two placement teams0/1 are supported.
    Native producers supply complete XY surface indices. Omission is reserved
    for synthetic fixtures whose selected surface is explicitly index zero.
    """
    cells = list(cells)
    if not cells or len({(x, y) for x, y, z in cells}) != len(cells):
        raise ValueError("Arena requires one selected altitude per cell")
    x0, x1 = min(c[0] for c in cells), max(c[0] for c in cells)
    y0, y1 = min(c[1] for c in cells), max(c[1] for c in cells)
    width, height = x1 - x0 + 1, y1 - y0 + 1
    if width * height > 32767:
        raise ValueError("Arena bounds too large")
    masks = [0x100] * (width * height)
    flags = bytearray([255] * len(masks))
    available = {(x, y): z for x, y, z in cells}
    if surface_indices is not None and (
        not isinstance(surface_indices, dict)
        or set(surface_indices) != set(available)
        or any(
            not isinstance(key, tuple)
            or len(key) != 2
            or any(type(coordinate) is not int for coordinate in key)
            for key in surface_indices
        )
        or any(
            type(value) is not int or not 0 <= value <= 63
            for value in surface_indices.values()
        )
    ):
        raise ValueError("Invalid or incomplete native arena surface indices")
    borders = {tuple(cell) for cell in border_cells}
    if not borders <= set(cells):
        raise ValueError("Native arena border cell is not a selected surface")
    for x, y in available:
        masks[(y - y0) * width + x - x0] = (
            0 if surface_indices is None else surface_indices[(x, y)]
        ) | (128 if (x, y, available[(x, y)]) in borders else 0)
    # fct trailing (byte,int) pairs are QL obstacle occupancies, not team slots.
    # Placement lives only in the cell_flags array.
    teams = [] if obstacle_values is None else list(obstacle_values)
    if (
        len(teams) > 127
        or len({entry[0] for entry in teams}) != len(teams)
        or any(
            type(identity) is not int
            or not 0 <= identity <= 126
            or type(index) is not int
            or not 0 <= index < width * height
            for identity, index in teams
        )
    ):
        raise ValueError("Invalid native obstacle occupancy metadata")
    seen = set()
    for team, group in placement.items():
        group = (
            [group]
            if isinstance(group, (tuple, list))
            and len(group) == 3
            and all(type(n) is int for n in group)
            else list(group)
        )
        if not group:
            raise ValueError("Empty placement team")
        for cell in group:
            x, y, z = cell
            if team not in (0, 1) or available.get((x, y)) != z or (x, y) in seen:
                raise ValueError("Invalid or overlapping placement cell")
            seen.add((x, y))
            index = (y - y0) * width + x - x0
            flags[index] = team
    if set(placement) != {0, 1}:
        raise ValueError("Both placement teams are required")
    return dict(
        map_id=map_id,
        instance_id=instance_id,
        x=x0,
        y=y0,
        width=width,
        height=height,
        min_z=min(c[2] for c in cells),
        max_z=max(c[2] for c in cells),
        cell_masks=masks,
        cell_flags=bytes(flags),
        flag_R=0,
        flag_S=0,
        team_values=teams,
    )


def initial_timeline(actor_ids, order):
    """SU/Tc/SX/fem placement timeline, no statuses or turn progress.

    The two SX ID arrays hold available members and initial ordered members.
    Tc bsx=-1 is the captured no-current-member sentinel. No timers are copied.
    """
    actor_ids = list(actor_ids)
    order = list(order)
    if (
        not actor_ids
        or len(actor_ids) > 127
        or len(set(actor_ids)) != len(actor_ids)
        or set(order) != set(actor_ids)
        or len(order) != len(actor_ids)
    ):
        raise ValueError("Invalid initial timeline membership")
    out = struct.pack(">hiBq", 0, 0, 0, 0)
    for ids in (actor_ids, order):
        out += struct.pack(">b", len(ids)) + b"".join(
            struct.pack(">q", identity) for identity in ids
        )
    out += struct.pack(">b", len(actor_ids)) + b"".join(
        struct.pack(">qh", identity, 0) for identity in actor_ids
    )
    out += b"\xff\x00" + struct.pack(">b", len(actor_ids))
    out += b"".join(struct.pack(">qi", identity, 0) for identity in actor_ids)
    return out
