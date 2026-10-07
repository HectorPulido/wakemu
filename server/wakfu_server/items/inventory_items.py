"""Authoritative minimal items. No items are granted by character creation.

Rich item options, equipment eligibility and item effects require separate
native rules; these operations fail before changing ownership or quantity.
"""
import struct


def load(db, character_id):
    from .inventory_elements import hydrate
    from .inventory_shards import hydrate as hydrate_shards
    from .mount_inventory import hydrate as hydrate_mounts

    return hydrate_mounts(
        db,
        hydrate_shards(
            db,
            hydrate(
                db,
                [
                    dict(row)
                    for row in db.execute(
                        "SELECT * FROM inventory_items WHERE character_id=%s ORDER BY container,slot",
                        (character_id,),
                    )
                ],
            ),
        ),
    )


def _lease(store, db, account_id, generation, character_id):
    row = db.execute(
        """SELECT character_id FROM sessions WHERE account_id=%s
        AND generation=%s AND expires_at>%s FOR UPDATE""",
        (account_id, generation, store.now()),
    ).fetchone()
    if row is None or row["character_id"] != character_id:
        raise ValueError("Invalid inventory session")
    if (
        db.execute(
            "SELECT id FROM characters WHERE id=%s AND account_id=%s FOR UPDATE",
            (character_id, account_id),
        ).fetchone()
        is None
    ):
        raise ValueError("Invalid inventory owner")


def grant(
    store,
    account_id,
    generation,
    character_id,
    *,
    reference,
    quantity,
    container,
    slot,
    allowed_references
):
    """Explicit local grant; callers must supply their verified item catalog."""
    if (
        type(reference) is not int
        or reference not in allowed_references
        or type(quantity) is not int
        or not 1 <= quantity <= 32767
        or type(slot) is not int
        or slot < 0
    ):
        raise ValueError("Invalid owned item grant")
    with store.connection() as db:
        _lease(store, db, account_id, generation, character_id)
        mount_model = db.execute(
            "SELECT model_id FROM mount_models WHERE reference=%s", (reference,)
        ).fetchone()
        if mount_model is not None and quantity != 1:
            raise ValueError("Mount grants require one unstacked unit")
        bag = db.execute(
            "SELECT * FROM inventory_containers WHERE uid=%s AND character_id=%s",
            (container, character_id),
        ).fetchone()
        if bag is None or slot >= bag["capacity"]:
            raise ValueError("Invalid owned destination container")
        if db.execute(
            "SELECT 1 FROM inventory_items WHERE container=%s AND slot=%s",
            (container, slot),
        ).fetchone():
            raise ValueError("Inventory position occupied")
        # Shared sequence covers items, bags and reserved client split IDs.
        from .inventory_uids import allocate

        uid = allocate(db)
        db.execute(
            "INSERT INTO inventory_items(uid,character_id,reference,quantity,container,slot) VALUES(%s,%s,%s,%s,%s,%s)",
            (uid, character_id, reference, quantity, container, slot),
        )
        item = dict(
            db.execute("SELECT * FROM inventory_items WHERE uid=%s", (uid,)).fetchone()
        )
        from .inventory_elements import create, save

        selected = create(reference)
        if selected is not None:
            save(db, uid, selected)
            item.update(selected)
        if mount_model is not None:
            from .mount_inventory import initialize

            item["mount"] = initialize(db, uid, character_id, store.now())
        return item


def remove(store, account_id, generation, character_id, uid, quantity):
    if type(quantity) is not int or not 1 <= quantity <= 32767:
        raise ValueError("Invalid removal quantity")
    with store.connection() as db:
        _lease(store, db, account_id, generation, character_id)
        item = db.execute(
            "SELECT * FROM inventory_items WHERE uid=%s AND character_id=%s",
            (uid, character_id),
        ).fetchone()
        if item is None or quantity > item["quantity"]:
            raise ValueError("Item unavailable or foreign")
        character = store.character(account_id, character_id, db)
        from wakfu_server.wire import proto_fields

        for build in character["builds"].values():
            for tag, value in proto_fields(bytes.fromhex(build["equipment"])):
                if tag == 10 and dict(proto_fields(value)).get(8) == uid:
                    raise ValueError(
                        "Equipped item must be removed from its build first"
                    )
        if quantity == item["quantity"]:
            db.execute("DELETE FROM inventory_items WHERE uid=%s", (uid,))
        else:
            db.execute(
                "UPDATE inventory_items SET quantity=quantity-%s WHERE uid=%s",
                (quantity, uid),
            )
        # cwZ/chK -> fnq/fnp -> Rj.b adds this signed quantity delta.
        return (12470, struct.pack(">qh", uid, -quantity))


def _varint(value):
    result = bytearray()
    while value > 127:
        result.append((value & 127) | 128)
        value >>= 7
    result.append(value)
    return bytes(result)


def item_proto(item):
    uid, ref, qty = (item[k] for k in ("uid", "reference", "quantity"))
    if (
        type(uid) is not int
        or not 0 < uid < (1 << 63)
        or type(ref) is not int
        or not 0 < ref < (1 << 31)
        or type(qty) is not int
        or not 1 <= qty <= 32767
    ):
        raise ValueError("Invalid minimal item")
    from .inventory_elements import proto
    from .inventory_shards import proto as shard_proto

    mount_proto = b""
    if "mount" in item:
        if qty != 1:
            raise ValueError("Mount protobuf requires an unstacked unit")
        from .mount_codec import item_pet

        mount_proto = item_pet(item["mount"])

    return (
        b"\x08"
        + _varint(uid)
        + b"\x10"
        + _varint(ref)
        + b"\x18"
        + _varint(qty)
        + proto(item)
        + shard_proto(item)
        + mount_proto
    )


def equipment_inventory(character):
    """cxC13078: independent hR registry resolving equipment-sheet unit IDs.

    chZ loads hR through fpi.a into bIM/fpd and refreshes an open build panel.
    A physical12471 insertion alone does not populate this separate registry.
    hR field1 repeats kX item protobufs; these are owned minimal item records.
    """
    from wakfu_server.wire import proto_field

    identity = character["id"]
    if type(identity) is not int or not 0 < identity < (1 << 63):
        raise ValueError("Invalid equipment inventory owner")
    items = character.get("inventory_items", [])
    if any(item["character_id"] != identity for item in items):
        raise ValueError("Foreign equipment inventory unit")
    if len({item["uid"] for item in items}) != len(items):
        raise ValueError("Duplicate equipment inventory unit")
    blob = b"".join(proto_field(10, item_proto(item)) for item in items)
    return 13078, struct.pack(">qIB", identity, len(blob), 0) + blob


def item_form(item):
    item_proto(item)
    from .inventory_elements import binary_options

    return struct.pack(
        ">qih", item["uid"], item["reference"], item["quantity"]
    ) + binary_options(item)


def insertion(item, *, notification=False):
    proto = item_proto(item)
    return (
        12471,
        struct.pack(">qhI", item["container"], item["slot"], len(proto))
        + proto
        + bytes((bool(notification),)),
    )


def decode_equip(body):
    if len(body) != 25:
        raise ValueError("Invalid12656 request length")
    uid, source, character_id, slot = struct.unpack(">qqqb", body)
    if uid <= 0 or source <= 0 or character_id <= 0 or slot < 0:
        raise ValueError("Invalid equipped item identity")
    return dict(uid=uid, container=source, character_id=character_id, slot=slot)


def decode_use(body):
    if (
        len(body) not in (9, 19)
        or body[8] not in (0, 1)
        or len(body) != 9 + body[8] * 10
    ):
        raise ValueError("Invalid12659 request")
    uid = struct.unpack_from(">q", body)[0]
    if uid <= 0:
        raise ValueError("Invalid item UID")
    return dict(
        uid=uid, position=struct.unpack_from(">iih", body, 9) if body[8] else None
    )


def decode_action(body):
    if len(body) < 12:
        raise ValueError("Invalid13220 request")
    action_id, uid = struct.unpack_from(">iq", body)
    if action_id <= 0 or uid <= 0:
        raise ValueError("Invalid item action identity")
    return dict(action_id=action_id, uid=uid, parameters=body[12:])


def owned_request(store, account_id, generation, character_id, opcode, body):
    """Resolve a native request to an owned item without executing its effect."""
    decoder = {12656: decode_equip, 12659: decode_use, 13220: decode_action}.get(opcode)
    if decoder is None:
        raise ValueError("Unsupported inventory request")
    request = decoder(body)
    with store.connection() as db:
        _lease(store, db, account_id, generation, character_id)
        item = db.execute(
            "SELECT * FROM inventory_items WHERE uid=%s AND character_id=%s",
            (request["uid"], character_id),
        ).fetchone()
        if item is None:
            raise ValueError("Item unavailable or foreign")
        if opcode == 12656 and (
            request["character_id"] != character_id
            or request["container"] != item["container"]
        ):
            raise ValueError("Foreign equipment destination or item source")
        return request, dict(item)
