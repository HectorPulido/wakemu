"""Original fdp/fdq microbot owner networks, separate from fighter turns."""
from .combat_casting_range import int32
from .combat_trove_int_map import NativeTroveIntMap

SOURCE = "fcb.f_fdp.b_fdq.a_j"


def _distance(a, b):
    def absolute(value):
        value = int32(value)
        return value if value == -(1 << 31) else abs(value)

    distance = int32(absolute(a[0] - b[0]) + absolute(a[1] - b[1]))
    return 0 if distance <= 1 else int32(distance - 1)


def _insert_sorted(rows, row):
    # ayJ.add uses Collections.binarySearch, including equal-key insertion.
    low, high = 0, len(rows) - 1
    while low <= high:
        middle = (low + high) >> 1
        a, b = rows[middle]["cell"], row["cell"]
        comparison = int32(int32(a[0] - b[0]) + int32(a[1] - b[1]))
        if comparison < 0:
            low = middle + 1
        elif comparison > 0:
            high = middle - 1
        else:
            low = middle
            break
    rows.insert(low, row)


def build_microbot_segments(rows, maximum_distance, segment_is_passable):
    """fdq.j and fdl extension; rows retain actual registration encounter order."""
    if (
        type(maximum_distance) is not int
        or not -(1 << 31) <= maximum_distance < (1 << 31)
        or not callable(segment_is_passable)
    ):
        raise ValueError("Missing actual microbot range or Sn authority")
    groups = ({}, {})
    maps = (NativeTroveIntMap(), NativeTroveIntMap())
    for row in rows:
        cell = row.get("cell")
        if (
            not isinstance(cell, (tuple, list))
            or len(cell) != 3
            or any(type(value) is not int for value in cell)
            or not -(1 << 15) <= cell[2] < (1 << 15)
        ):
            raise ValueError("Invalid actual microbot coordinate")
        for axis in (0, 1):
            key = cell[axis]
            maps[axis].put(key)
            _insert_sorted(groups[axis].setdefault(key, []), row)
    segments = []
    for axis in (0, 1):
        for key in maps[axis].order():
            previous = current_segment = None
            for row in groups[axis][key]:
                point = tuple(row["cell"])
                if previous is not None:
                    start = tuple(previous["cell"])
                    aligned = start != point and (
                        start[0] == point[0] or start[1] == point[1]
                    )
                    if not aligned or _distance(start, point) > maximum_distance:
                        current_segment = None
                    else:
                        passable = segment_is_passable(start, point)
                        if type(passable) is not bool:
                            raise ValueError("Missing actual microbot Sn result")
                        if not passable:
                            current_segment = None
                        else:
                            if current_segment is not None:
                                lo, hi = current_segment
                                rank = int32(point[0] + point[1])
                                endpoint = (
                                    lo
                                    if rank < int32(lo[0] + lo[1])
                                    else hi
                                    if rank > int32(hi[0] + hi[1])
                                    else None
                                )
                                if (
                                    endpoint is not None
                                    and _distance(endpoint, point) <= maximum_distance
                                ):
                                    current_segment[0 if endpoint == lo else 1] = point
                                else:
                                    current_segment = None
                            if current_segment is None:
                                endpoints = [start, point]
                                if int32(start[0] + start[1]) >= int32(
                                    point[0] + point[1]
                                ):
                                    endpoints.reverse()
                                current_segment = endpoints
                                segments.append(current_segment)
                previous = row
    return tuple((tuple(lo), tuple(hi)) for lo, hi in segments)


def microbot_cells(segments, surface_z):
    """fdl/aBw inclusive cells with actual QI.X altitude; membership only."""
    if not callable(surface_z):
        raise ValueError("Missing actual microbot QI.X authority")
    cells = set()
    for lo, hi in segments:
        axis = 0 if lo[1] == hi[1] else 1
        for coordinate in range(lo[axis], hi[axis] + 1):
            x, y = (coordinate, lo[1]) if axis == 0 else (lo[0], coordinate)
            z = surface_z(x, y)
            if type(z) is not int or not -(1 << 15) <= z < (1 << 15):
                raise ValueError("Missing actual microbot QI.X short altitude")
            cells.add((x, y, z))
    return frozenset(cells)


def _networks(fight):
    networks = getattr(fight, "native_microbot_networks", {})
    if not isinstance(networks, dict):
        raise ValueError("Missing actual microbot owner networks")
    return networks


def preflight_microbot_owner(fight, owner_id):
    """fdp captures owner shM once when its owner entry is first allocated."""
    if type(owner_id) is not int or owner_id == 0:
        raise ValueError("Missing actual microbot owner identity")
    existing = _networks(fight).get(owner_id)
    if existing is not None:
        if (
            not isinstance(existing, dict)
            or existing.get("source") != SOURCE
            or type(existing.get("maximum_distance")) is not int
            or not isinstance(existing.get("microbot_ids"), list)
        ):
            raise ValueError("Invalid actual microbot owner network")
        return existing["maximum_distance"]
    from .combat_summon_initialization import registered_or_detached_actor

    owner = registered_or_detached_actor(fight, owner_id)
    stats = getattr(owner, "effect_stats", None)
    # A missing dictionary key is not evidence for native PV.a(shM)==false.
    if not isinstance(stats, dict) or type(stats.get(93)) is not int:
        raise ValueError("Missing actual microbot owner shM characteristic")
    return stats[93]


def _rebuild(fight, network):
    from .combat_microbot_path import microbot_path_projection

    projection = microbot_path_projection(fight)
    areas = getattr(fight, "native_effect_areas", {})
    rows = []
    for uid in network["microbot_ids"]:
        row = areas.get(uid)
        if (
            not isinstance(row, dict)
            or row.get("native_faw_constructor", {}).get("kind") != 4
            or row.get("owner_id") != network["owner_id"]
        ):
            raise ValueError("Missing actual registered microbot")
        rows.append(row)
    segments = build_microbot_segments(
        rows, network["maximum_distance"], projection.segment_is_passable
    )
    cells = microbot_cells(segments, projection.surface_z)
    network["segments"] = [[list(lo), list(hi)] for lo, hi in segments]
    # This represents HashSet membership only, never native iteration order.
    network["cells"] = [list(cell) for cell in sorted(cells)]


def register_microbot(fight, row):
    maximum = preflight_microbot_owner(fight, row.get("owner_id"))
    networks = _networks(fight)
    owner_id, uid = row["owner_id"], row["uid"]
    network = networks.get(owner_id)
    if network is None:
        network = dict(
            source=SOURCE,
            owner_id=owner_id,
            maximum_distance=maximum,
            microbot_ids=[],
            segments=[],
            cells=[],
        )
        networks[owner_id] = network
    if uid in network["microbot_ids"]:
        raise ValueError("Duplicate microbot registration")
    network["microbot_ids"].append(uid)
    _rebuild(fight, network)
    row["native_microbot_network_source"] = SOURCE
    fight.native_microbot_networks = networks


def unregister_microbot(fight, row):
    networks = _networks(fight)
    network = networks.get(row.get("owner_id"))
    if (
        not isinstance(network, dict)
        or network.get("source") != SOURCE
        or row.get("uid") not in network.get("microbot_ids", [])
    ):
        raise ValueError("Missing actual microbot removal registration")
    network["microbot_ids"].remove(row["uid"])
    _rebuild(fight, network)
    # fdp.c does not remove its empty owner entry or recapture shM.
