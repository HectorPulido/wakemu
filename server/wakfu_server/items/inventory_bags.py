"""Native ordinary bag removal/equipping, preserving its item UID.

The permanent30-cell base bag remains fixed. Specialized bag filters and bag-slot replacement remain unsupported.
"""
import struct
from .inventory_items import _lease, insertion, decode_equip
from .inventory_bag_rules import ordinary


def remove(store, account_id, generation, character_id, body):
    if len(body) != 33:
        raise ValueError("Invalid13673 bag removal length")
    destination, bag_uid, source, repeated_destination, position = struct.unpack(
        ">qqqqb", body
    )
    if (
        destination <= 0
        or destination != repeated_destination
        or source != bag_uid
        or position < -1
    ):
        raise ValueError("Invalid native bag removal identity")
    with store.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        _lease(store, db, account_id, generation, character_id)
        bag = db.execute(
            "SELECT * FROM inventory_containers WHERE uid=? AND character_id=?",
            (bag_uid, character_id),
        ).fetchone()
        target = db.execute(
            "SELECT * FROM inventory_containers WHERE uid=? AND character_id=?",
            (destination, character_id),
        ).fetchone()
        if bag is None or bag["kind"] == 0 or target is None or target["kind"] != 0:
            raise ValueError("Foreign, fixed or unsupported bag")
        rule = ordinary(bag["reference"])
        if bag["capacity"] != rule["capacity"]:
            raise ValueError("Bag capacity differs from native catalog")
        if db.execute(
            "SELECT 1 FROM inventory_items WHERE container=?", (bag_uid,)
        ).fetchone():
            raise ValueError("Bag must be empty before removal")
        occupied = {
            entry[0]
            for entry in db.execute(
                "SELECT slot FROM inventory_items WHERE container=?", (destination,)
            )
        }
        if position == -1:
            position = next(
                (slot for slot in range(target["capacity"]) if slot not in occupied), -1
            )
        if not 0 <= position < target["capacity"] or position in occupied:
            raise ValueError("Bag destination is full or occupied")
        db.execute("DELETE FROM inventory_containers WHERE uid=?", (bag_uid,))
        db.execute(
            "INSERT INTO inventory_items(uid,character_id,reference,quantity,container,slot) VALUES(?,?,?,?,?,?)",
            (bag_uid, character_id, bag["reference"], 1, destination, position),
        )
        item = dict(
            db.execute(
                "SELECT * FROM inventory_items WHERE uid=?", (bag_uid,)
            ).fetchone()
        )
        return dict(
            character=store.character(account_id, character_id, db),
            packets=[
                (13172, struct.pack(">qq", character_id, bag_uid)),
                insertion(item),
            ],
        )


def equip(store, account_id, generation, character_id, body):
    request = decode_equip(body)
    if request["character_id"] != character_id or request["slot"] not in (1, 2, 3):
        raise ValueError("Foreign or unsupported bag slot")
    with store.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        _lease(store, db, account_id, generation, character_id)
        item = db.execute(
            "SELECT * FROM inventory_items WHERE uid=? AND character_id=?",
            (request["uid"], character_id),
        ).fetchone()
        if (
            item is None
            or item["quantity"] != 1
            or item["container"] != request["container"]
        ):
            raise ValueError("Unavailable or unsupported owned bag item")
        rule = ordinary(item["reference"])
        character = store.character(account_id, character_id, db)
        if character.get("effective_level", character["level"]) < rule["minimum_level"]:
            raise ValueError("Native bag minimum level requirement not met")
        if db.execute(
            "SELECT 1 FROM inventory_containers WHERE character_id=? AND kind=?",
            (character_id, request["slot"]),
        ).fetchone():
            raise ValueError("Bag slot occupied; native replacement not implemented")
        db.execute("DELETE FROM inventory_items WHERE uid=?", (item["uid"],))
        db.execute(
            "INSERT INTO inventory_containers(character_id,uid,reference,kind,capacity,flags) VALUES(?,?,?,?,?,?)",
            (
                character_id,
                item["uid"],
                item["reference"],
                request["slot"],
                rule["capacity"],
                0,
            ),
        )
        bag = struct.pack(
            ">qiBhBHH",
            item["uid"],
            item["reference"],
            request["slot"],
            rule["capacity"],
            0,
            0,
            0,
        )
        return dict(
            character=store.character(account_id, character_id, db),
            packets=[
                (12470, struct.pack(">qh", item["uid"], -1)),
                (12919, struct.pack(">qI", character_id, len(bag)) + bag),
            ],
        )
