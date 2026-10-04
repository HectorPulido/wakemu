"""Native12804 minimal-item transfer; client performs the visual move first."""
from .paths import DATA_ROOT
import struct
import json
from pathlib import Path
from .inventory_items import _lease

STACKS = {
    entry["reference"]: entry
    for entry in json.loads((DATA_ROOT / "item-stack-rules.json").read_text())["items"]
}


def decode(body):
    if len(body) not in (27, 37):
        raise ValueError("Invalid native item transfer length")
    uid, destination, source, position, split = struct.unpack_from(">qqqhB", body)
    if (
        uid <= 0
        or destination <= 0
        or source <= 0
        or position < -1
        or split not in (0, 1)
    ):
        raise ValueError("Invalid native item transfer fields")
    if len(body) != 27 + 10 * split:
        raise ValueError("Invalid native item split payload")
    clone, quantity = struct.unpack_from(">qh", body, 27) if split else (None, None)
    if split and (clone <= 0 or clone == uid or quantity <= 0 or position < 0):
        raise ValueError("Invalid partial transfer identity or quantity")
    return dict(
        uid=uid,
        destination=destination,
        source=source,
        position=position,
        clone_uid=clone,
        quantity=quantity,
    )


def transfer(store, account_id, generation, character_id, body):
    request = decode(body)
    with store.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        _lease(store, db, account_id, generation, character_id)
        from .inventory_uids import schema

        schema(db)
        clone = request["clone_uid"]
        if clone is not None:
            reservation = db.execute(
                "SELECT * FROM inventory_reserved_uids WHERE uid=? AND account_id=? AND generation=? AND character_id=?",
                (clone, account_id, generation, character_id),
            ).fetchone()
            if reservation is None:
                raise ValueError("Partial item UID was not reserved by this session")
            if reservation["used_request"] is not None:
                if bytes(reservation["used_request"]) != body:
                    raise ValueError(
                        "Reserved item UID already consumed by another request"
                    )
                return dict(
                    character=store.character(account_id, character_id, db),
                    packets=[],
                    applied=False,
                )
        item = db.execute(
            "SELECT * FROM inventory_items WHERE uid=? AND character_id=?",
            (request["uid"], character_id),
        ).fetchone()
        destination = db.execute(
            "SELECT * FROM inventory_containers WHERE uid=? AND character_id=?",
            (request["destination"], character_id),
        ).fetchone()
        source = db.execute(
            "SELECT * FROM inventory_containers WHERE uid=? AND character_id=?",
            (request["source"], character_id),
        ).fetchone()
        if (
            item is None
            or source is None
            or destination is None
            or item["container"] != source["uid"]
            or source["kind"] not in (0, 1, 2, 3)
            or destination["kind"] not in (0, 1, 2, 3)
        ):
            raise ValueError("Foreign item/container or unsupported container type")
        rule = STACKS.get(item["reference"])
        if rule is None or not 1 <= item["quantity"] <= rule["maximum"]:
            raise ValueError(
                "Unknown native item stack rule or oversized owned quantity"
            )
        quantity = item["quantity"] if clone is None else request["quantity"]
        if clone is not None and quantity >= item["quantity"]:
            raise ValueError("Partial transfer must leave an owned source remainder")
        position = request["position"]
        if position == -1:
            occupied = {
                entry[0]
                for entry in db.execute(
                    "SELECT slot FROM inventory_items WHERE container=?",
                    (destination["uid"],),
                )
            }
            position = next(
                (
                    index
                    for index in range(destination["capacity"])
                    if index not in occupied
                ),
                -1,
            )
        if not 0 <= position < destination["capacity"]:
            raise ValueError("Inventory destination full or outside capacity")
        other = db.execute(
            "SELECT * FROM inventory_items WHERE container=? AND slot=?",
            (destination["uid"], position),
        ).fetchone()
        if other is not None and other["uid"] == item["uid"]:
            if clone is not None:
                raise ValueError("Cannot split item into itself")
            return dict(
                character=store.character(account_id, character_id, db),
                packets=[],
                applied=False,
            )
        merge = (
            other is not None
            and other["reference"] == item["reference"]
            and rule["minimal_mergeable"]
        )
        if other is not None and not merge and clone is not None:
            raise ValueError("Native partial transfer cannot swap incompatible items")
        if merge:
            if (
                other["character_id"] != character_id
                or not 1 <= other["quantity"] <= rule["maximum"]
            ):
                raise ValueError("Invalid destination stack ownership or quantity")
            # A minimal build selects individual units; a merge must not leave
            # persisted selection references dangling or turn one unit into a stack.
            from .wire import proto_fields

            character = store.character(account_id, character_id, db)
            for build in character["builds"].values():
                for tag, value in proto_fields(bytes.fromhex(build["equipment"])):
                    if tag == 10 and dict(proto_fields(value)).get(8) in (
                        item["uid"],
                        other["uid"],
                    ):
                        raise ValueError(
                            "Desequip the selected unit before merging its stack"
                        )
            moved = min(quantity, rule["maximum"] - other["quantity"])
            db.execute(
                "UPDATE inventory_items SET quantity=quantity+? WHERE uid=?",
                (moved, other["uid"]),
            )
            if moved == item["quantity"]:
                db.execute("DELETE FROM inventory_items WHERE uid=?", (item["uid"],))
            else:
                db.execute(
                    "UPDATE inventory_items SET quantity=quantity-? WHERE uid=?",
                    (moved, item["uid"]),
                )
        elif other is not None:
            # Both native containers are ordinary bags: exchange their two
            # owned records without ever exposing a duplicate UNIQUE slot.
            db.execute(
                "UPDATE inventory_items SET slot=32767 WHERE uid=?", (item["uid"],)
            )
            db.execute(
                "UPDATE inventory_items SET container=?,slot=? WHERE uid=?",
                (source["uid"], item["slot"], other["uid"]),
            )
            db.execute(
                "UPDATE inventory_items SET container=?,slot=? WHERE uid=?",
                (destination["uid"], position, item["uid"]),
            )
        elif clone is not None:
            db.execute(
                "UPDATE inventory_items SET quantity=quantity-? WHERE uid=?",
                (quantity, item["uid"]),
            )
            db.execute(
                "INSERT INTO inventory_items(uid,character_id,reference,quantity,container,slot) VALUES(?,?,?,?,?,?)",
                (
                    clone,
                    character_id,
                    item["reference"],
                    quantity,
                    destination["uid"],
                    position,
                ),
            )
        else:
            db.execute(
                "UPDATE inventory_items SET container=?,slot=? WHERE uid=?",
                (destination["uid"], position, item["uid"]),
            )
        if clone is not None:
            db.execute(
                "UPDATE inventory_reserved_uids SET used_request=? WHERE uid=?",
                (body, clone),
            )
        # biB/flW updated the client before cpR was sent: duplicate12471 would
        # trigger inventory duplication. Persistence needs no success mutation.
        return dict(
            character=store.character(account_id, character_id, db),
            packets=[],
            applied=True,
        )


def synchronization(character):
    from .inventory import bags

    return 13713, struct.pack(">q", character["id"]) + bags(character)
