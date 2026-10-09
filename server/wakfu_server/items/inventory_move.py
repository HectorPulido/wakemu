"""Native12804 minimal-item transfer; client performs the visual move first."""
from wakfu_server import native_catalog as protocol_catalog
from .paths import DATA_ROOT
import struct
import json
from pathlib import Path
from .inventory_items import _lease

STACKS = {
    entry["reference"]: entry
    for entry in protocol_catalog.load(DATA_ROOT / "item-stack-rules.json")["items"]
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
        _lease(store, db, account_id, generation, character_id)
        clone = request["clone_uid"]
        if clone is not None:
            reservation = db.execute(
                "SELECT * FROM inventory_reserved_uids WHERE uid=%s AND account_id=%s AND generation=%s AND character_id=%s",
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
            "SELECT * FROM inventory_items WHERE uid=%s AND character_id=%s",
            (request["uid"], character_id),
        ).fetchone()
        destination = db.execute(
            "SELECT * FROM inventory_containers WHERE uid=%s AND character_id=%s",
            (request["destination"], character_id),
        ).fetchone()
        source = db.execute(
            "SELECT * FROM inventory_containers WHERE uid=%s AND character_id=%s",
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
                entry["slot"]
                for entry in db.execute(
                    "SELECT slot FROM inventory_items WHERE container=%s",
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
            "SELECT * FROM inventory_items WHERE container=%s AND slot=%s",
            (destination["uid"], position),
        ).fetchone()
        socketed = {
            row["uid"]
            for row in db.execute(
                "SELECT uid FROM inventory_item_shards WHERE uid=ANY(%s)",
                ([item["uid"]] + ([] if other is None else [other["uid"]]),),
            )
        }
        if clone is not None and item["uid"] in socketed:
            raise ValueError("Socketed item cannot be split")
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
            if socketed:
                raise ValueError("Socketed items cannot be merged")
            from .inventory_elements import hydrate, masks

            source_item, target_item = hydrate(db, [dict(item), dict(other)])
            if masks(source_item) != masks(target_item):
                raise ValueError("Native element selections differ; units cannot merge")
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
                "UPDATE inventory_items SET quantity=quantity+%s WHERE uid=%s",
                (moved, other["uid"]),
            )
            if moved == item["quantity"]:
                db.execute("DELETE FROM inventory_items WHERE uid=%s", (item["uid"],))
            else:
                db.execute(
                    "UPDATE inventory_items SET quantity=quantity-%s WHERE uid=%s",
                    (moved, item["uid"]),
                )
        elif other is not None:
            # Both native containers are ordinary bags: exchange their two
            # owned records without ever exposing a duplicate UNIQUE slot.
            db.execute(
                "UPDATE inventory_items SET slot=32767 WHERE uid=%s", (item["uid"],)
            )
            db.execute(
                "UPDATE inventory_items SET container=%s,slot=%s WHERE uid=%s",
                (source["uid"], item["slot"], other["uid"]),
            )
            db.execute(
                "UPDATE inventory_items SET container=%s,slot=%s WHERE uid=%s",
                (destination["uid"], position, item["uid"]),
            )
        elif clone is not None:
            db.execute(
                "UPDATE inventory_items SET quantity=quantity-%s WHERE uid=%s",
                (quantity, item["uid"]),
            )
            db.execute(
                "INSERT INTO inventory_items(uid,character_id,reference,quantity,container,slot) VALUES(%s,%s,%s,%s,%s,%s)",
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
                "UPDATE inventory_items SET container=%s,slot=%s WHERE uid=%s",
                (destination["uid"], position, item["uid"]),
            )
        if clone is not None:
            from .inventory_elements import copy as copy_elements

            if not merge:
                copy_elements(db, item["uid"], clone)
            db.execute(
                "UPDATE inventory_reserved_uids SET used_request=%s WHERE uid=%s",
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

    # eHf.BAGS (ordinal 35) selects only eHe.BAGS. cwY13713/chK
    # passes the remainder to eHd.ew, whose first byte is a format ID.
    return 13713, struct.pack(">qB", character["id"], 35) + bags(character)


def reload_inventory(store, account_id, character):
    """Refresh committed inventory without replacing live combat/map state."""
    saved = store.character(account_id, character["id"])
    return dict(
        character,
        inventory_containers=saved["inventory_containers"],
        inventory_items=saved["inventory_items"],
    )
