"""PostgreSQL-owned haven-bag configuration; no captured account state."""
from wakfu_server import native_catalog as protocol_catalog
from .paths import DATA_ROOT
import json
from psycopg.types.json import Jsonb
from pathlib import Path

MODELS = {
    model["id"]
    for model in protocol_catalog.load(DATA_ROOT / "haven-bag-models.json")["models"]
}
FURNITURE_TEMPLATES = {
    item["template_id"]
    for item in protocol_catalog.load(DATA_ROOT / "haven-bag-furniture-templates.json")[
        "templates"
    ]
    if item["java_type"].split(":")[0]
    in {
        "Decoration",
        "FxDecoration",
        "BackgroundDisplay",
        "DimensionalBagBackgroundDisplay",
        "PortableCraftTable",
    }
}


GEM_TYPES = {
    4262: 0,
    11098: 0,
    4263: 1,
    11100: 1,
    4264: 2,
    27572: 3,
    4266: 4,
    11099: 4,
    27573: 5,
    27574: 6,
    27575: 7,
}


def initial_layout(character_id):
    return [
        dict(
            index=index,
            enabled=index == 0,
            primary_ref=4262 if index == 0 else -1,
            primary_uid=character_id * 256 + 1 if index == 0 else 0,
            secondary_ref=-1,
            secondary_uid=0,
        )
        for index in range(9)
    ]


def owner_id(db, character_id):
    """Resolve the durable account bag without changing physical item identities."""
    row = db.execute(
        "SELECT b.character_id FROM account_haven_bags b "
        "JOIN characters c ON c.account_id=b.account_id WHERE c.id=%s",
        (character_id,),
    ).fetchone()
    if row is None:
        raise ValueError("Missing account haven bag")
    return row["character_id"]


def instance_id(character):
    return (character.get("haven_bag") or {}).get("owner_id", character["id"])


def load(db, character_id):
    character_id = owner_id(db, character_id)
    row = db.execute(
        "SELECT * FROM haven_bags WHERE character_id=%s",
        (character_id,),
    ).fetchone()
    if row is None:
        raise ValueError("Missing owned haven bag")
    return {
        "owner_id": character_id,
        "appearance_id": row["appearance_id"],
        "rooms": row["layout"],
        "locked": row["locked"],
        "furniture": row["furniture"],
        "access": row["access"],
    }


def save(
    store,
    account_id,
    generation,
    character_id,
    *,
    appearance_id=None,
    rooms=None,
    locked=None,
    access=None,
    furniture=None,
):
    with store.connection() as db:
        bag_id = owner_id(db, character_id)
    if appearance_id is not None and (
        type(appearance_id) is not int or appearance_id not in MODELS
    ):
        raise ValueError("Invalid haven-bag appearance")
    if rooms is not None:
        if not isinstance(rooms, list) or not 1 <= len(rooms) <= 9:
            raise ValueError("Invalid haven-bag room list")
        base = next((room for room in rooms if room.get("index") == 0), None)
        if (
            base is None
            or base.get("enabled") is not True
            or base.get("primary_ref") != 4262
            or base.get("primary_uid") != bag_id * 256 + 1
        ):
            raise ValueError(
                "The fixed entrance room and its owned base gem must remain intact"
            )
        indexes = set()
        gem_uids = set()
        for room in rooms:
            if (
                not isinstance(room, dict)
                or type(room.get("index")) is not int
                or not 0 <= room["index"] < 9
            ):
                raise ValueError("Invalid haven-bag room index")
            if room["index"] in indexes:
                raise ValueError("Duplicate haven-bag room index")
            indexes.add(room["index"])
            if type(room.get("enabled")) is not bool:
                raise ValueError("Invalid haven-bag room status")
            for key in ("primary_ref", "secondary_ref", "primary_uid", "secondary_uid"):
                if type(room.get(key)) is not int or not (
                    -1 if key.endswith("_ref") else 0
                ) <= room[key] < (1 << (31 if key.endswith("_ref") else 63)):
                    raise ValueError("Invalid haven-bag gem")
            for slot in ("primary", "secondary"):
                ref, uid = room[slot + "_ref"], room[slot + "_uid"]
                if ref == -1:
                    if uid:
                        raise ValueError("Absent gem has an item UID")
                elif ref not in GEM_TYPES or uid <= 0 or uid in gem_uids:
                    raise ValueError("Unknown or duplicated haven-bag gem")
                else:
                    gem_uids.add(uid)
            if room["secondary_ref"] != -1 and (
                room["primary_ref"] == -1
                or GEM_TYPES[room["primary_ref"]] != GEM_TYPES[room["secondary_ref"]]
            ):
                raise ValueError("Secondary gem does not match primary type")
    if furniture is not None:
        from wakfu_server.haven_bag_furniture import encode_vf, decode_vf

        if not isinstance(furniture, list) or len(furniture) > 1000:
            raise ValueError("Invalid haven-bag furniture list")
        seen = set()
        templates = set()
        for item in furniture:
            if (
                type(item.get("deployed")) is not bool
                or type(item.get("room")) is not int
                or not 0 <= item["room"] < 9
            ):
                raise ValueError("Invalid haven-bag furniture placement")
            if item.get("quantity", 1) != 1:
                raise ValueError(
                    "Furniture stacks require splitting into unique units, unsupported"
                )
            form = {
                key: value
                for key, value in item.items()
                if key not in ("deployed", "room")
            }
            decode_vf(encode_vf(**form))
            if item["template_id"] not in FURNITURE_TEMPLATES:
                raise ValueError("Unknown haven-bag furniture template")
            if item["item_uid"] in seen:
                raise ValueError("Duplicate haven-bag furniture item")
            seen.add(item["item_uid"])
            if item["template_id"] in templates:
                raise ValueError(
                    "Repeated templates need dynamic instance IDs, currently unsupported"
                )
            templates.add(item["template_id"])
    if locked is not None and type(locked) is not bool:
        raise ValueError("Invalid haven-bag lock")
    with store.connection() as db:
        store.lock_character(db, account_id, generation, character_id)
        db.execute(
            "SELECT character_id FROM haven_bags WHERE character_id=%s FOR UPDATE",
            (bag_id,),
        )
        current = load(db, character_id)
        if rooms is not None:
            by_index = {room["index"]: room for room in rooms}
            for plant in db.execute(
                "SELECT DISTINCT (x / 6) * 3 + (y / 6) AS room_index "
                "FROM planted_resources WHERE map_id=9 AND instance_id=%s",
                (bag_id,),
            ):
                previous = next(
                    (
                        room
                        for room in current["rooms"]
                        if room["index"] == plant["room_index"]
                    ),
                    None,
                )
                if previous != by_index.get(plant["room_index"]):
                    raise ValueError(
                        "Remove garden plants before changing the room gems"
                    )
        if rooms is not None:
            # Native room rearrangement moves physical gems as well as floor
            # visuals. Preserve their durable ownership coordinates so a
            # later reconnect/removal finds the same unit in its new slot.
            gems = list(
                db.execute(
                    "SELECT * FROM haven_bag_gems WHERE character_id=%s FOR UPDATE",
                    (bag_id,),
                )
            )
            destinations = {}
            for room in rooms:
                for primary, key in ((True, "primary"), (False, "secondary")):
                    if room[key + "_ref"] != -1:
                        destinations[room[key + "_uid"]] = (
                            room["index"],
                            primary,
                            room[key + "_ref"],
                        )
            for gem in gems:
                destination = destinations.get(gem["uid"])
                if destination is None or destination[2] != gem["reference"]:
                    raise ValueError("Room rearrangement cannot discard an owned gem")
            if gems:
                # Slot uniqueness is immediate, so swap all coordinates in a
                # single owner transaction by replacing the same owned rows.
                db.execute(
                    "DELETE FROM haven_bag_gems WHERE character_id=%s", (bag_id,)
                )
                for gem in gems:
                    room_index, primary_slot, _reference = destinations[gem["uid"]]
                    db.execute(
                        "INSERT INTO haven_bag_gems(uid,account_id,character_id,room_index,primary_slot,reference,source_uid,damage_elements,resistance_elements,shard_state) "
                        "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                        (
                            gem["uid"],
                            gem["account_id"],
                            bag_id,
                            room_index,
                            primary_slot,
                            gem["reference"],
                            gem["source_uid"],
                            gem["damage_elements"],
                            gem["resistance_elements"],
                            gem["shard_state"],
                        ),
                    )
        if access is not None:
            from wakfu_server.haven_bag import permission_payload, decode_permissions
            import struct

            payload = permission_payload({"locked": False, "access": access})
            _, access = decode_permissions(struct.pack(">I", len(payload)) + payload)
            for item in access["characters"]:
                target = db.execute(
                    "SELECT name FROM characters WHERE id=%s", (item["id"],)
                ).fetchone()
                if target is None or target["name"] != item["name"]:
                    raise ValueError("Unknown local haven-bag permission character")
        db.execute(
            "UPDATE haven_bags SET appearance_id=%s,layout=%s,locked=%s,access=%s,furniture=%s WHERE character_id=%s",
            (
                current["appearance_id"] if appearance_id is None else appearance_id,
                Jsonb(current["rooms"] if rooms is None else rooms),
                current["locked"] if locked is None else locked,
                Jsonb(current["access"] if access is None else access),
                Jsonb(current["furniture"] if furniture is None else furniture),
                bag_id,
            ),
        )
        return store.character(account_id, character_id, db)


def rearrange_rooms(config, body):
    """crJ13210: move/swap owned gems between two room slots.

    fvw.nQ(true) selects primary; false selects secondary. Room0's fixed
    primary cannot be removed. Empty targets always receive a primary gem,
    matching fvs.b(BZBZZ). No inventory item can be created by this operation.
    """
    import copy
    import struct

    if len(body) != 4:
        raise ValueError("Invalid haven-bag gem move")
    primary_source, primary_target, source, target = struct.unpack(">BBbb", body)
    if primary_source not in (0, 1) or primary_target not in (0, 1):
        raise ValueError("Invalid haven-bag gem slot")
    if not (0 <= source < 9 and 0 <= target < 9) or source == target:
        raise ValueError("Invalid haven-bag gem room")
    rooms = copy.deepcopy(config["rooms"])
    by_index = {room["index"]: room for room in rooms}
    if source not in by_index:
        raise ValueError("Source room has no owned gem")
    src = by_index[source]
    dst = by_index.get(target)
    if dst is None:
        dst = dict(
            index=target,
            enabled=False,
            primary_ref=-1,
            primary_uid=0,
            secondary_ref=-1,
            secondary_uid=0,
        )
        rooms.append(dst)
    sk = "primary" if primary_source else "secondary"
    dk = "primary" if primary_target else "secondary"

    def gem(room, key):
        return room[key + "_ref"], room[key + "_uid"]

    def set_gem(room, key, value):
        room[key + "_ref"], room[key + "_uid"] = value

    owned = gem(src, sk)
    if owned[0] == -1 or not owned[1]:
        raise ValueError("Source slot has no owned gem")
    other = gem(dst, dk)
    if primary_source and source == 0:
        raise ValueError("The fixed entrance gem cannot be moved")
    if primary_target and target == 0 and other[0] != -1:
        raise ValueError("The fixed entrance gem cannot be replaced")
    if primary_source and (
        src["secondary_ref"] != -1
        or any(
            item.get("deployed") and item.get("room") == source
            for item in config.get("furniture", [])
        )
    ):
        raise ValueError("Room primary cannot be removed")
    if other[0] == -1:
        if dst["primary_ref"] != -1:
            if primary_target or GEM_TYPES[owned[0]] != GEM_TYPES[dst["primary_ref"]]:
                raise ValueError("Empty secondary requires a matching primary gem")
            target_slot = "secondary"
        else:
            target_slot = "primary"
        set_gem(src, sk, (-1, 0))
        set_gem(dst, target_slot, owned)
    else:
        if primary_source and src["secondary_ref"] != -1:
            raise ValueError("Primary has an attached secondary")
        if primary_target and dst["secondary_ref"] != -1:
            raise ValueError("Target primary has an attached secondary")
        if not primary_source and GEM_TYPES[owned[0]] != GEM_TYPES[other[0]]:
            raise ValueError("Secondary gem type does not match its room")
        if not primary_target and GEM_TYPES[owned[0]] != GEM_TYPES[dst["primary_ref"]]:
            raise ValueError("Secondary gem type does not match target room")
        set_gem(src, sk, other)
        set_gem(dst, dk, owned)
    for room in rooms:
        room["enabled"] = room["index"] == 0 or room["primary_ref"] != -1
    return sorted(rooms, key=lambda room: room["index"])


def deploy_furniture(config, body):
    import copy
    from wakfu_server.haven_bag_furniture import decode_deploy_request

    request = decode_deploy_request(body)
    x, y = request["x"], request["y"]
    if not (0 <= x < 18 and 0 <= y < 18) or request["z"] != 0:
        raise ValueError("Furniture must be on the haven-bag room floor")
    room_id = (x // 6) * 3 + y // 6
    room = next((room for room in config["rooms"] if room["index"] == room_id), None)
    if room is None or not room.get("enabled") or room["primary_ref"] == -1:
        raise ValueError("Furniture room has no owned gem")
    furniture = copy.deepcopy(config["furniture"])
    owned = next(
        (
            item
            for item in furniture
            if item["item_uid"] == request["item_uid"]
            and item["item_ref"] == request["item_ref"]
        ),
        None,
    )
    if owned is None or owned["deployed"]:
        raise ValueError("Furniture item is not available in this owned bag")
    if any(
        item["deployed"] and (item["x"], item["y"], item["z"]) == (x, y, request["z"])
        for item in furniture
    ):
        raise ValueError("Furniture destination is occupied")
    owned.update(request, deployed=True, room=room_id)
    return furniture


def edit_furniture(config, opcode, body):
    """Resolve native dynamic instance IDs and legacy template-addressed actions."""
    import copy
    import struct

    furniture = copy.deepcopy(config["furniture"])
    if opcode == 12870:
        if len(body) != 12 or body[10:] != b"\x00\x00":
            raise ValueError("Invalid itemizable action body")
        template_id, action = struct.unpack(">qH", body[:10])
        if action not in (23, 29):
            raise ValueError("Unsupported itemizable action")
    elif opcode == 12363:
        if len(body) != 22:
            raise ValueError("Invalid itemizable move body")
        template_id, x, y, z, direction = struct.unpack(">qiihi", body)
        if not 0 <= direction < 8:
            raise ValueError("Invalid itemizable move direction")
        action = 27
    else:
        raise ValueError("Unsupported itemizable opcode")
    candidates = [
        item
        for item in furniture
        if item["deployed"] and template_id in (item["item_uid"], item["template_id"])
    ]
    if len(candidates) != 1:
        raise ValueError("Itemizable element is not uniquely owned in this bag")
    item = candidates[0]
    if action == 23:
        item["deployed"] = False
    elif action == 29:
        # Our local server rotates furniture clockwise by one quarter turn.
        item["direction"] = (item.get("direction", 0) + 2) % 8
    else:
        if not (0 <= x < 18 and 0 <= y < 18) or z != 0:
            raise ValueError("Furniture must be on the haven-bag room floor")
        room_id = (x // 6) * 3 + y // 6
        room = next(
            (room for room in config["rooms"] if room["index"] == room_id), None
        )
        if room is None or not room.get("enabled") or room["primary_ref"] == -1:
            raise ValueError("Furniture destination room has no owned gem")
        if any(
            other is not item
            and other["deployed"]
            and (other["x"], other["y"], other["z"]) == (x, y, z)
            for other in furniture
        ):
            raise ValueError("Furniture destination is occupied")
        item.update(x=x, y=y, z=z, direction=direction, room=room_id)
    return furniture
