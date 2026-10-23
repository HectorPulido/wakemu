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
        _lease(store, db, account_id, generation, character_id)
        bag = db.execute(
            "SELECT * FROM inventory_containers WHERE uid=%s AND character_id=%s FOR UPDATE",
            (bag_uid, character_id),
        ).fetchone()
        target = db.execute(
            "SELECT * FROM inventory_containers WHERE uid=%s AND character_id=%s FOR UPDATE",
            (destination, character_id),
        ).fetchone()
        if bag is None or bag["kind"] == 0 or target is None or target["kind"] != 0:
            raise ValueError("Foreign, fixed or unsupported bag")
        rule = ordinary(bag["reference"])
        if bag["capacity"] != rule["capacity"]:
            raise ValueError("Bag capacity differs from native catalog")
        if db.execute(
            "SELECT 1 FROM inventory_items WHERE container=%s", (bag_uid,)
        ).fetchone():
            raise ValueError("Bag must be empty before removal")
        occupied = {
            entry["slot"]
            for entry in db.execute(
                "SELECT slot FROM inventory_items WHERE container=%s", (destination,)
            )
        }
        if position == -1:
            position = next(
                (slot for slot in range(target["capacity"]) if slot not in occupied), -1
            )
        if not 0 <= position < target["capacity"] or position in occupied:
            raise ValueError("Bag destination is full or occupied")
        db.execute("DELETE FROM inventory_containers WHERE uid=%s", (bag_uid,))
        db.execute(
            "INSERT INTO inventory_items(uid,character_id,reference,quantity,container,slot) VALUES(%s,%s,%s,%s,%s,%s)",
            (bag_uid, character_id, bag["reference"], 1, destination, position),
        )
        from .portable_item_custody import restore

        restore(
            db,
            uid=bag_uid,
            account_id=account_id,
            character_id=character_id,
            reference=bag["reference"],
            kind="bag",
        )
        character = store.character(account_id, character_id, db)
        item = next(
            item for item in character["inventory_items"] if item["uid"] == bag_uid
        )
        return dict(
            character=character,
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
        _lease(store, db, account_id, generation, character_id)
        item = db.execute(
            "SELECT * FROM inventory_items WHERE uid=%s AND character_id=%s FOR UPDATE",
            (request["uid"], character_id),
        ).fetchone()
        if item is None or item["container"] != request["container"]:
            raise ValueError("Unavailable or unsupported owned bag item")
        rule = ordinary(item["reference"])
        character = store.character(account_id, character_id, db)
        if character.get("effective_level", character["level"]) < rule["minimum_level"]:
            raise ValueError("Native bag minimum level requirement not met")
        if db.execute(
            "SELECT 1 FROM inventory_containers WHERE character_id=%s AND kind=%s",
            (character_id, request["slot"]),
        ).fetchone():
            raise ValueError("Bag slot occupied; native replacement not implemented")
        from .inventory_uids import allocate
        from .portable_item_custody import hold

        bag_uid = item["uid"] if item["quantity"] == 1 else allocate(db)
        hold(db, item, uid=bag_uid, account_id=account_id, kind="bag")
        if item["quantity"] == 1:
            db.execute("DELETE FROM inventory_items WHERE uid=%s", (bag_uid,))
        else:
            db.execute(
                "UPDATE inventory_items SET quantity=quantity-1 WHERE uid=%s",
                (item["uid"],),
            )
        db.execute(
            "INSERT INTO inventory_containers(character_id,uid,reference,kind,capacity,flags) VALUES(%s,%s,%s,%s,%s,%s)",
            (
                character_id,
                bag_uid,
                item["reference"],
                request["slot"],
                rule["capacity"],
                0,
            ),
        )
        bag = struct.pack(
            ">qiBhBHH",
            bag_uid,
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
