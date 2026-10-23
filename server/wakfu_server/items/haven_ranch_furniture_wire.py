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


def context(
    owner_account_id,
    map_id,
    area_ids,
    items,
    now_ms,
    *,
    building_states=(),
    buildings_by_sector=None,
    creatures_by_sector=None,
    paddocks_by_sector=None,
    rewards=(),
):
    """czY13864/fBE with native areas and furniture, without invented animals.

    Area identifiers must come from the installed fBm.gxf terrain definitions,
    not from biome building slots (fBm.gxg). The caller supplies that authority.
    """
    owner = _integer(owner_account_id, 1, 9223372036854775807, "owner")
    world = _integer(map_id, 1, 9223372036854775807, "world")
    return 13864, struct.pack(">qqB", owner, world, 1) + biome_record(
        area_ids,
        items,
        now_ms,
        building_states=building_states,
        buildings_by_sector=buildings_by_sector,
        creatures_by_sector=creatures_by_sector,
        paddocks_by_sector=paddocks_by_sector,
        rewards=rewards,
    )


def biome_record(
    area_ids,
    items,
    now_ms,
    *,
    building_states=(),
    buildings_by_sector=None,
    creatures_by_sector=None,
    paddocks_by_sector=None,
    rewards=(),
):
    """Encode the shared original fBE for scene and account component 18."""
    clock = _integer(now_ms, 1, 9223372036854775807, "clock")
    areas = list(area_ids)
    if not areas or len(areas) != len(set(areas)):
        raise ValueError("Ranch context requires distinct accredited terrain areas")
    buildings_by_sector = {} if buildings_by_sector is None else buildings_by_sector
    if not isinstance(buildings_by_sector, dict) or set(buildings_by_sector) - set(
        areas
    ):
        raise ValueError("Native Ranch buildings reference an unknown terrain area")
    creatures_by_sector = {} if creatures_by_sector is None else creatures_by_sector
    paddocks_by_sector = {} if paddocks_by_sector is None else paddocks_by_sector
    for collection in (creatures_by_sector, paddocks_by_sector):
        if not isinstance(collection, dict) or set(collection) - set(areas):
            raise ValueError("Native Ranch herd references an unknown terrain area")
        if any(not isinstance(rows, (list, tuple)) for rows in collection.values()):
            raise ValueError("Native Ranch herd sector requires a row sequence")
    from .haven_ranch_herd_wire import encode_creature, encode_paddock

    creature_uids = set()
    paddock_uids = set()
    for area, rows in creatures_by_sector.items():
        for row in rows:
            paddock = next(
                (
                    p
                    for p in paddocks_by_sector.get(area, ())
                    if p["uid"] == row["native_tJU"]
                ),
                None,
            )
            if paddock is None or row["native_tJT"] is not False:
                raise ValueError("Ranch sector animal has no matching owned paddock")
            cells = {
                tuple(cell)
                for cell in tuple(paddock["interior"]) + tuple(paddock["boundary"])
            }
            if (row["x"], row["y"]) not in cells:
                raise ValueError("Ranch animal lies outside its referenced paddock")
            encode_creature(row)
            if row["uid"] in creature_uids:
                raise ValueError("Duplicate native Ranch creature UID")
            creature_uids.add(row["uid"])
    for area, rows in paddocks_by_sector.items():
        for row in rows:
            if row["sector_id"] != area or row["uid"] in paddock_uids:
                raise ValueError(
                    "Ranch paddock has inconsistent sector or duplicate UID"
                )
            encode_paddock(row)
            paddock_uids.add(row["uid"])
    grouped = {area: [] for area in areas}
    grouped_buildings = {area: [] for area in areas}
    from wakfu_server.haven_ranch_building_wire import building_record

    seen_building_uids = set()
    for area, rows in buildings_by_sector.items():
        if not isinstance(rows, (list, tuple)):
            raise ValueError("Native Ranch sector buildings must be a row sequence")
        for row in rows:
            uid = _integer(row["uid"], 1, 9223372036854775807, "building UID")
            if uid in seen_building_uids:
                raise ValueError("Duplicate native Ranch building UID")
            seen_building_uids.add(uid)
            grouped_buildings[area].append(building_record(row))
    identities = set()
    for area in areas:
        _integer(area, 0, 2147483647, "area")
    for item in items:
        if item["area_id"] not in grouped or item["item_uid"] in identities:
            raise ValueError("Unknown Ranch furniture area or duplicate identity")
        identities.add(item["item_uid"])
        grouped[item["area_id"]].append(furniture_record(item))
    payload = struct.pack(">i", len(areas))
    for area in sorted(areas):
        records = grouped[area]
        building_records = grouped_buildings[area]
        # Original fBV: fBG buildings, fBM scene objects, group->fBS lists,
        # deployed fBQ animals and fBT bridges. fxS also carries all owned fBQ.
        payload += struct.pack(">ii", area, len(building_records))
        payload += b"".join(building_records)
        payload += struct.pack(">i", len(records)) + b"".join(records)
        groups = {}
        for paddock in paddocks_by_sector.get(area, ()):
            groups.setdefault(paddock["group"], []).append(paddock)
        payload += struct.pack(">i", len(groups))
        for group, rows in sorted(groups.items()):
            _integer(group, -2147483648, 2147483647, "paddock group")
            _integer(len(rows), 0, 32767, "paddock count")
            payload += struct.pack(">ih", group, len(rows))
            payload += b"".join(
                encode_paddock(row) for row in sorted(rows, key=lambda r: r["uid"])
            )
        animals = creatures_by_sector.get(area, ())
        payload += struct.pack(">i", len(animals))
        payload += b"".join(
            encode_creature(row) for row in sorted(animals, key=lambda r: r["uid"])
        )
        payload += struct.pack(">i", 0)  # No account-owned fBT bridge instances.
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
    # Native fBE writes the map size followed by full fBU values, without keys.
    from wakfu_server.ranch_reward_retrieval import encode_reward

    if not isinstance(rewards, (list, tuple)):
        raise ValueError("Native Ranch rewards require a row sequence")
    _integer(len(rewards), 0, 2147483647, "reward count")
    reward_uids = set()
    encoded_rewards = []
    for reward in rewards:
        encoded = encode_reward(reward)
        if reward["uid"] in reward_uids:
            raise ValueError("Duplicate native Ranch reward UID")
        reward_uids.add(reward["uid"])
        encoded_rewards.append((reward["uid"], encoded))
    payload += struct.pack(">i", len(encoded_rewards))
    payload += b"".join(record for _, record in sorted(encoded_rewards))
    return payload + struct.pack(">q", clock)


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
