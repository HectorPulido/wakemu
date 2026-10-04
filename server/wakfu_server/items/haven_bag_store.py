"""SQLite-owned haven-bag configuration; no captured account state."""
from .paths import DATA_ROOT
import json
from pathlib import Path

MODELS = {
    model["id"]
    for model in json.loads((DATA_ROOT / "haven-bag-models.json").read_text())["models"]
}
FURNITURE_TEMPLATES = {
    item["template_id"]
    for item in json.loads(
        (DATA_ROOT / "haven-bag-furniture-templates.json").read_text()
    )["templates"]
    if item["java_type"].split(":")[0]
    in {"Decoration", "FxDecoration", "BackgroundDisplay", "PortableCraftTable"}
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


def schema(db):
    db.execute(
        """CREATE TABLE IF NOT EXISTS haven_bags (
        character_id INTEGER PRIMARY KEY REFERENCES characters(id) ON DELETE CASCADE,
        appearance_id INTEGER NOT NULL DEFAULT 408,
        layout TEXT NOT NULL,
        locked INTEGER NOT NULL DEFAULT 0,
        furniture TEXT NOT NULL DEFAULT '[]',
        access TEXT NOT NULL DEFAULT '{"groups":[{"group":0,"rights":1}],"characters":[]}')"""
    )
    columns = {row["name"] for row in db.execute("PRAGMA table_info(haven_bags)")}
    for name, default in (
        ("furniture", "[]"),
        ("access", '{"groups":[{"group":0,"rights":1}],"characters":[]}'),
    ):
        if name not in columns:
            db.execute(
                f"ALTER TABLE haven_bags ADD COLUMN {name} TEXT NOT NULL DEFAULT '{default}'"
            )


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


def load(db, character_id):
    db.execute(
        "INSERT OR IGNORE INTO haven_bags(character_id,layout,access) VALUES(?,?,?)",
        (
            character_id,
            json.dumps(initial_layout(character_id), separators=(",", ":")),
            json.dumps(
                {"groups": [{"group": 0, "rights": 1}], "characters": []},
                separators=(",", ":"),
            ),
        ),
    )
    row = db.execute(
        "SELECT * FROM haven_bags WHERE character_id=?", (character_id,)
    ).fetchone()
    access = json.loads(row["access"])
    if "allow" in access or "deny" in access:
        if access.get("allow") or access.get("deny"):
            raise ValueError("Unsupported legacy haven-bag ACL data")
        access = {"groups": [{"group": 0, "rights": 1}], "characters": []}
        db.execute(
            "UPDATE haven_bags SET access=? WHERE character_id=?",
            (json.dumps(access, separators=(",", ":")), character_id),
        )
    rooms = json.loads(row["layout"])
    # Previous minimal serializer duplicated the same item in two slots.
    # Repair only that impossible state, preserving legitimate personalization.
    changed = False
    for room in rooms:
        if room["primary_uid"] and room["primary_uid"] == room["secondary_uid"]:
            room["secondary_ref"], room["secondary_uid"] = -1, 0
            changed = True
    present = {room["index"] for room in rooms}
    for index in range(9):
        if index not in present:
            rooms.append(
                dict(
                    index=index,
                    enabled=False,
                    primary_ref=-1,
                    primary_uid=0,
                    secondary_ref=-1,
                    secondary_uid=0,
                )
            )
            changed = True
    rooms.sort(key=lambda room: room["index"])
    if changed:
        db.execute(
            "UPDATE haven_bags SET layout=? WHERE character_id=?",
            (json.dumps(rooms, separators=(",", ":")), character_id),
        )
    return {
        "appearance_id": row["appearance_id"],
        "rooms": rooms,
        "locked": bool(row["locked"]),
        "furniture": json.loads(row["furniture"]),
        "access": {
            "groups": access.get("groups", []),
            "characters": access.get("characters", []),
        },
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
            or base.get("primary_uid") != character_id * 256 + 1
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
        db.execute("BEGIN IMMEDIATE")
        session = db.execute(
            "SELECT character_id FROM sessions WHERE account_id=? AND generation=? AND expires_at>?",
            (account_id, generation, store.clock()),
        ).fetchone()
        if session is None or session["character_id"] != character_id:
            raise ValueError("Sesión o personaje inválidos.")
        store.character(account_id, character_id, db)
        current = load(db, character_id)
        if access is not None:
            from wakfu_server.haven_bag import permission_payload, decode_permissions
            import struct

            payload = permission_payload({"locked": False, "access": access})
            _, access = decode_permissions(struct.pack(">I", len(payload)) + payload)
            for item in access["characters"]:
                target = db.execute(
                    "SELECT name FROM characters WHERE id=?", (item["id"],)
                ).fetchone()
                if target is None or target["name"] != item["name"]:
                    raise ValueError("Unknown local haven-bag permission character")
        db.execute(
            "UPDATE haven_bags SET appearance_id=?,layout=?,locked=?,access=?,furniture=? WHERE character_id=?",
            (
                current["appearance_id"] if appearance_id is None else appearance_id,
                json.dumps(
                    current["rooms"] if rooms is None else rooms, separators=(",", ":")
                ),
                current["locked"] if locked is None else locked,
                json.dumps(
                    current["access"] if access is None else access,
                    separators=(",", ":"),
                ),
                json.dumps(
                    current["furniture"] if furniture is None else furniture,
                    separators=(",", ":"),
                ),
                character_id,
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
    if primary_source and (
        (src["enabled"] and other[0] == -1)
        or src["secondary_ref"] != -1
        or any(item.get("room") == source for item in config.get("furniture", []))
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
    return sorted(rooms, key=lambda room: room["index"])


def deploy_furniture(config, body):
    import copy
    from wakfu_server.haven_bag_furniture import decode_deploy_request

    request = decode_deploy_request(body)
    x, y = request["x"], request["y"]
    if not (0 <= x < 18 and 0 <= y < 18):
        raise ValueError("Furniture must be inside a haven-bag room")
    room_id = (x // 6) * 3 + y // 6
    room = next((room for room in config["rooms"] if room["index"] == room_id), None)
    if room is None or room["primary_ref"] == -1:
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
    """Modern itemizable actions use Re.Sn (template ID), not vj.item UID."""
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
        if item["deployed"] and item["template_id"] == template_id
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
        if not (0 <= x < 18 and 0 <= y < 18):
            raise ValueError("Furniture must be inside a haven-bag room")
        room_id = (x // 6) * 3 + y // 6
        room = next(
            (room for room in config["rooms"] if room["index"] == room_id), None
        )
        if room is None or room["primary_ref"] == -1:
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
