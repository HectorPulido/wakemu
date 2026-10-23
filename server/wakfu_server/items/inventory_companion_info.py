"""Original ProtoItem54/companionInfo.xp and vm/tE transferred companion XP."""
import struct


def hydrate(db, items):
    if not items:
        return items
    by_uid = {item["uid"]: item for item in items}
    for row in db.execute(
        "SELECT uid,xp FROM inventory_item_companions WHERE uid=ANY(%s)",
        (list(by_uid),),
    ):
        by_uid[row["uid"]]["companion_xp"] = row["xp"]
    return items


def proto(item):
    from wakfu_server.wire import proto_field

    xp = item.get("companion_xp")
    if xp is None:
        return b""
    if type(xp) is not int or not 0 <= xp < 2**63 or item["quantity"] != 1:
        raise ValueError("Invalid unlinked companion XP unit")
    return proto_field(434, proto_field(8, xp))


def binary_option(item):
    if "companion_xp" not in item:
        return b"\x00"
    proto(item)
    return b"\x01" + struct.pack(">q", item["companion_xp"])
