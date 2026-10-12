"""Original Ranch decoration messages, separate from the haven-bag vf model.

csn12766 is reference based: it does not authorize a physical inventory UID.
czV12259 installs an fBM into the owner's ceK area model; the physical scene
interactive must additionally be published using cwG13664.
"""
import struct


def _integer(value, minimum, maximum, label):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError("Invalid Ranch furniture " + label)
    return value


def decode_deploy(body):
    if not isinstance(body, bytes) or len(body) != 16:
        raise ValueError("Ranch furniture placement requires exactly 16 bytes")
    reference, direction, x, y = struct.unpack(">iiii", body)
    _integer(reference, 1, 2147483647, "reference")
    _integer(direction, 0, 7, "direction")
    # Actual native surface and area membership are checked by the authority;
    # these limits only prevent overflow of the packed interactive position.
    _integer(x, -131071, 131072, "x")
    _integer(y, -131071, 131072, "y")
    return dict(item_ref=reference, direction=direction, x=x, y=y)


def furniture_record(item):
    """Encode fBM without a parent container or opaque item-specific payload."""
    identity = _integer(item["item_uid"], 1, 9223372036854775807, "identity")
    reference = _integer(item["item_ref"], 1, 2147483647, "reference")
    direction = _integer(item["direction"], 0, 7, "direction")
    x = _integer(item["x"], -131071, 131072, "x")
    y = _integer(item["y"], -131071, 131072, "y")
    z = _integer(item["z"], -511, 512, "height")
    return struct.pack(">qqBiiihB", identity, reference, 0, direction, x, y, z, 0)


def add(scene_map_id, area_id, item):
    owner = _integer(scene_map_id, 1, 9223372036854775807, "scene map")
    area = _integer(area_id, 0, 2147483647, "area")
    return 12259, struct.pack(">qB", owner, 1) + furniture_record(item) + struct.pack(
        ">i", area
    )


def context(owner_account_id, map_id, area_ids, items, now_ms, *, building_states=()):
    """czY13864/fBE with native areas and furniture, without invented animals.

    Area identifiers must come from the installed fBm.gxf terrain definitions,
    not from biome building slots (fBm.gxg). The caller supplies that authority.
    """
    owner = _integer(owner_account_id, 1, 9223372036854775807, "owner")
    world = _integer(map_id, 1, 9223372036854775807, "world")
    clock = _integer(now_ms, 1, 9223372036854775807, "clock")
    areas = list(area_ids)
    if not areas or len(areas) != len(set(areas)):
        raise ValueError("Ranch context requires distinct accredited terrain areas")
    grouped = {area: [] for area in areas}
    identities = set()
    for area in areas:
        _integer(area, 0, 2147483647, "area")
    for item in items:
        if item["area_id"] not in grouped or item["item_uid"] in identities:
            raise ValueError("Unknown Ranch furniture area or duplicate identity")
        identities.add(item["item_uid"])
        grouped[item["area_id"]].append(furniture_record(item))
    payload = struct.pack(">qqBi", owner, world, 1, len(areas))
    for area in sorted(areas):
        records = grouped[area]
        # fBV: area, animals count, furniture count/records, production map,
        # paddock list and bridge list. Empty collections grant no extra feature.
        payload += struct.pack(">iii", area, 0, len(records)) + b"".join(records)
        payload += struct.pack(">iii", 0, 0, 0)
    # fBF uses native slot identity and fBq enum: ABSENT=0, PRESENT=1.
    buildings = []
    slots = set()
    for building in building_states:
        slot = _integer(building["slot_id"], 1, 2147483647, "building slot")
        state = _integer(building["state"], 0, 1, "building state")
        if slot in slots:
            raise ValueError("Duplicate Ranch building slot")
        slots.add(slot)
        buildings.append((slot, struct.pack(">iB", slot, state)))
    payload += struct.pack(">i", len(buildings))
    payload += b"".join(record for _, record in sorted(buildings))
    # Global animals and snapshot clock are independent from bridge state.
    return 13864, payload + struct.pack(">iq", 0, clock)


def moved(scene_map_id, item):
    furniture_record(item)
    _integer(scene_map_id, 1, 9223372036854775807, "scene map")
    return 12452, struct.pack(
        ">qBqBiii",
        scene_map_id,
        1,
        item["item_uid"],
        item["direction"],
        item["x"],
        item["y"],
        item["area_id"],
    )


def removed(scene_map_id, item):
    furniture_record(item)
    _integer(scene_map_id, 1, 9223372036854775807, "scene map")
    return 12780, struct.pack(
        ">qBqiB", scene_map_id, 1, item["item_uid"], item["area_id"], 0
    )


def decode_edit(opcode, body):
    if opcode == 12363 and len(body) == 22:
        identity, x, y, z, direction = struct.unpack(">qiihi", body)
        decode_deploy(struct.pack(">iiii", 1, direction, x, y))
        _integer(identity, 1, 9223372036854775807, "identity")
        return dict(item_uid=identity, x=x, y=y, z=z, direction=direction, remove=False)
    if opcode == 12870 and len(body) == 12:
        identity, action, parameter = struct.unpack(">qHH", body)
        _integer(identity, 1, 9223372036854775807, "identity")
        if action in (23, 29) and parameter == 0:
            return dict(item_uid=identity, remove=action == 23, rotate=action == 29)
    raise ValueError("Unsupported or malformed native Ranch decoration edit")
