"""Durable native item skin metadata, independent of the item's statistics."""
import struct


def reference(item):
    value = item.get("appearance_ref", 0)
    if type(value) is not int or not 0 <= value < 2**31:
        raise ValueError("Invalid owned item appearance reference")
    return value


def hydrate(db, items):
    if not items:
        return items
    appearances = {
        row["uid"]: row["appearance_ref"]
        for row in db.execute(
            "SELECT uid,appearance_ref FROM inventory_item_appearances WHERE uid=ANY(%s)",
            ([item["uid"] for item in items],),
        )
    }
    return [
        dict(item, appearance_ref=appearances[item["uid"]])
        if item["uid"] in appearances
        else item
        for item in items
    ]


def proto(item):
    """Original kX field58 mimiSymbicSkinRefId -> fox.y -> fnR.VW."""
    from wakfu_server.wire import proto_field

    value = reference(item)
    return proto_field(464, value) if value else b""


def binary_option(item):
    """Original final vj.vu option stores one big-endian appearance reference."""
    value = reference(item)
    return b"\x01" + struct.pack(">i", value) if value else b"\x00"


def copy(db, source_uid, target_uid):
    db.execute(
        "INSERT INTO inventory_item_appearances(uid,appearance_ref) "
        "SELECT %s,appearance_ref FROM inventory_item_appearances WHERE uid=%s",
        (target_uid, source_uid),
    )
