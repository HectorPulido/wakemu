"""Transactional physical inventory ownership for native haven-bag furniture."""
import copy
import struct

from psycopg.types.json import Jsonb

from .haven_bag_furniture import decode_deploy_request
from .haven_bag_store import deploy_furniture, edit_furniture


def _location(character_id, location):
    if (
        not isinstance(location, dict)
        or location.get("map_id") != 9
        or location.get("instance_id") != character_id
    ):
        raise ValueError("Furniture requires the owner's active haven bag")


def _config(db, character_id):
    row = db.execute(
        "SELECT layout,furniture FROM haven_bags WHERE character_id=%s FOR UPDATE",
        (character_id,),
    ).fetchone()
    if row is None:
        raise ValueError("Missing owned haven bag")
    return {
        "rooms": copy.deepcopy(row["layout"]),
        "furniture": copy.deepcopy(row["furniture"]),
    }


def _persist(db, character_id, furniture):
    db.execute(
        "UPDATE haven_bags SET furniture=%s WHERE character_id=%s",
        (Jsonb(furniture), character_id),
    )


def _plain_item(db, uid):
    # vf's exact minimal item form cannot represent these options. Never lose
    # physical state by silently converting an enhanced/equipped item.
    for table in (
        "inventory_item_elements",
        "inventory_item_shards",
        "inventory_mounts",
        "inventory_pets",
    ):
        if db.execute(f"SELECT 1 FROM {table} WHERE uid=%s", (uid,)).fetchone():
            raise ValueError("Furniture item has unsupported specific data")


def deploy(
    store, account_id, generation, character_id, body, *, location, resolver=None
):
    """Move exactly one owned inventory unit into a deployed vf item form."""
    # Verify the canonical account owner after locking the live character.
    request = decode_deploy_request(body)
    if resolver is None:
        from .haven_bag_furniture_catalog import resolve_item

        resolver = resolve_item
    definition = resolver(request["item_ref"])
    if definition is None or definition.get("kind") not in {
        "Decoration",
        "FxDecoration",
        "BackgroundDisplay",
        "DimensionalBagBackgroundDisplay",
        "PortableCraftTable",
    }:
        raise ValueError(
            "Item is not a supported haven-bag decoration or craft station"
        )
    with store.connection() as db:
        store.lock_character(db, account_id, generation, character_id)
        from .haven_bag_store import owner_id

        bag_id = owner_id(db, character_id)
        _location(bag_id, location)
        config = _config(db, bag_id)
        room_id = (request["x"] // 6) * 3 + request["y"] // 6
        room = next((row for row in config["rooms"] if row["index"] == room_id), None)
        if room is None or not room.get("enabled") or room.get("primary_ref") == -1:
            raise ValueError("Furniture requires an installed room gem")
        if db.execute(
            "SELECT 1 FROM planted_resources WHERE map_id=9 AND instance_id=%s AND x=%s AND y=%s",
            (bag_id, request["x"], request["y"]),
        ).fetchone():
            raise ValueError("Furniture destination contains a garden plant")
        from .haven_bag_furniture_knowledge import known

        if request["item_uid"] == definition["template_id"] and known(
            db, account_id, request["item_ref"]
        ):
            template = definition["template_id"]
            if any(item["template_id"] == template for item in config["furniture"]):
                raise ValueError("This furniture template is already installed")
            from .inventory_uids import allocate

            unit_uid = allocate(db)
            unit = dict(
                template_id=template,
                item_uid=unit_uid,
                item_ref=request["item_ref"],
                x=0,
                y=0,
                z=0,
                direction=0,
                virtual=True,
                quantity=1,
                deployed=False,
                room=0,
            )
            config["furniture"].append(unit)
            native_request = struct.pack(
                ">iqiihi",
                request["item_ref"],
                unit_uid,
                request["x"],
                request["y"],
                request["z"],
                request["direction"],
            )
            furniture = deploy_furniture(config, native_request)
            _persist(db, bag_id, furniture)
            return {
                "character": store.character(account_id, character_id, db),
                "packets": [],
            }
        uid = request["item_uid"]
        existing = next((f for f in config["furniture"] if f["item_uid"] == uid), None)
        if existing is not None:
            if existing["deployed"]:
                raise ValueError("Furniture unit is already deployed")
            furniture = deploy_furniture(config, body)
            packets = []
        else:
            if uid == definition["template_id"]:
                # cKB/cKC pass the native template ID in crM's second long;
                # older item-based entry points pass fnR.LV (physical UID).
                # Select an owned source deterministically; neither wire form
                # grants ownership or permits consuming another reference.
                item = db.execute(
                    "SELECT * FROM inventory_items WHERE character_id=%s AND reference=%s ORDER BY uid LIMIT 1 FOR UPDATE",
                    (character_id, request["item_ref"]),
                ).fetchone()
            else:
                item = db.execute(
                    "SELECT * FROM inventory_items WHERE uid=%s AND character_id=%s FOR UPDATE",
                    (uid, character_id),
                ).fetchone()
            if item is None or item["reference"] != request["item_ref"]:
                raise ValueError(
                    "Furniture item is unavailable or belongs to another owner"
                )
            uid = item["uid"]
            _plain_item(db, uid)
            template = definition["template_id"]
            if any(f["template_id"] == template for f in config["furniture"]):
                raise ValueError("This furniture template is already installed")
            from .inventory_uids import allocate

            unit_uid = uid if item["quantity"] == 1 else allocate(db)
            unit = dict(
                template_id=template,
                item_uid=unit_uid,
                item_ref=item["reference"],
                x=0,
                y=0,
                z=0,
                direction=0,
                virtual=False,
                quantity=1,
                deployed=False,
                room=0,
            )
            from .portable_item_custody import hold

            hold(db, item, uid=unit_uid, account_id=account_id, kind="furniture")
            config["furniture"].append(unit)
            physical_request = struct.pack(
                ">iqiihi",
                request["item_ref"],
                unit_uid,
                request["x"],
                request["y"],
                request["z"],
                request["direction"],
            )
            furniture = deploy_furniture(config, physical_request)
            if item["quantity"] == 1:
                db.execute("DELETE FROM inventory_items WHERE uid=%s", (uid,))
            else:
                db.execute(
                    "UPDATE inventory_items SET quantity=quantity-1 WHERE uid=%s",
                    (uid,),
                )
            packets = [(12470, struct.pack(">qh", uid, -1))]
        _persist(db, bag_id, furniture)
        return {
            "character": store.character(account_id, character_id, db),
            "packets": packets,
        }


def edit(store, account_id, generation, character_id, opcode, body, *, location):
    """Rotate/move owned furniture; packing returns its exact unit to inventory."""
    # Verify the canonical account owner after locking the live character.
    with store.connection() as db:
        store.lock_character(db, account_id, generation, character_id)
        from .haven_bag_store import owner_id

        bag_id = owner_id(db, character_id)
        _location(bag_id, location)
        config = _config(db, bag_id)
        furniture = edit_furniture(config, opcode, body)
        for item, old in zip(furniture, config["furniture"]):
            if item["deployed"] and (item["x"], item["y"], item["z"]) != (
                old["x"],
                old["y"],
                old["z"],
            ):
                if db.execute(
                    "SELECT 1 FROM planted_resources WHERE map_id=9 AND instance_id=%s AND x=%s AND y=%s",
                    (bag_id, item["x"], item["y"]),
                ).fetchone():
                    raise ValueError("Furniture destination contains a garden plant")
        packed = next(
            (
                item
                for item, old in zip(furniture, config["furniture"])
                if old["deployed"] and not item["deployed"]
            ),
            None,
        )
        packets = []
        if packed is not None and packed.get("virtual"):
            # Account collection furniture is reusable knowledge, not the
            # physical learning item that was consumed when it was learned.
            furniture.remove(packed)
            _persist(db, bag_id, furniture)
            return {
                "character": store.character(account_id, character_id, db),
                "packets": [],
            }
        if packed is not None:
            containers = list(
                db.execute(
                    "SELECT uid,capacity FROM inventory_containers WHERE character_id=%s ORDER BY uid FOR UPDATE",
                    (character_id,),
                )
            )
            occupied = {
                (row["container"], row["slot"])
                for row in db.execute(
                    "SELECT container,slot FROM inventory_items WHERE character_id=%s FOR UPDATE",
                    (character_id,),
                )
            }
            destination = next(
                (
                    (row["uid"], slot)
                    for row in containers
                    for slot in range(row["capacity"])
                    if (row["uid"], slot) not in occupied
                ),
                None,
            )
            if destination is None:
                raise ValueError("A free inventory slot is required to pack furniture")
            container, slot = destination
            db.execute(
                "INSERT INTO inventory_items(uid,character_id,reference,quantity,container,slot) VALUES(%s,%s,%s,1,%s,%s)",
                (packed["item_uid"], character_id, packed["item_ref"], container, slot),
            )
            from .portable_item_custody import restore

            restore(
                db,
                uid=packed["item_uid"],
                account_id=account_id,
                character_id=character_id,
                reference=packed["item_ref"],
                kind="furniture",
            )
            from .inventory_items import insertion

            restored = store.character(account_id, character_id, db)
            restored_item = next(
                item
                for item in restored["inventory_items"]
                if item["uid"] == packed["item_uid"]
            )
            packets.append(insertion(restored_item))
            furniture.remove(packed)
        _persist(db, bag_id, furniture)
        return {
            "character": store.character(account_id, character_id, db),
            "packets": packets,
        }
