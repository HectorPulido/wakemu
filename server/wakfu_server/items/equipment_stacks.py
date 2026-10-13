"""Split equipment before native UI publication without losing owned units."""


def ensure_singleton(db, character_id, uid):
    """Separate one owned unit in the caller's locked action transaction.

    Keep the requested UID so references and operation receipts stay valid.
    Reserve just one ordinary bag slot for the remainder. A failed action must
    roll back this transaction as well as its own mutations.
    """
    from wakfu_server.inventory_uids import allocate

    items = list(
        db.execute(
            "SELECT * FROM inventory_items WHERE character_id=%s ORDER BY container,slot FOR UPDATE",
            (character_id,),
        )
    )
    item = next((row for row in items if row["uid"] == uid), None)
    if item is None:
        raise ValueError("Item UID is not owned by this character")
    if item["quantity"] == 1:
        return item
    occupied = {(row["container"], row["slot"]) for row in items}
    destination = next(
        (
            (bag["uid"], slot)
            for bag in db.execute(
                "SELECT uid,capacity FROM inventory_containers WHERE character_id=%s "
                "AND kind BETWEEN 0 AND 3 ORDER BY kind",
                (character_id,),
            )
            for slot in range(bag["capacity"])
            if (bag["uid"], slot) not in occupied
        ),
        None,
    )
    if destination is None:
        raise ValueError("Inventory needs one free slot to separate this item stack")
    remainder_uid = allocate(db)
    db.execute(
        "INSERT INTO inventory_items(uid,character_id,reference,quantity,container,slot) "
        "VALUES(%s,%s,%s,%s,%s,%s)",
        (
            remainder_uid,
            character_id,
            item["reference"],
            item["quantity"] - 1,
            *destination,
        ),
    )
    for table, columns in (
        ("inventory_item_elements", "damage_elements,resistance_elements"),
        ("inventory_item_bindings", "bound,template_reference"),
        ("inventory_item_recycling_state", "unidentified,socketed"),
        ("inventory_item_shards", "shard_state"),
    ):
        db.execute(
            f"INSERT INTO {table}(uid,{columns}) SELECT %s,{columns} FROM {table} WHERE uid=%s",
            (remainder_uid, uid),
        )
    return db.execute(
        "UPDATE inventory_items SET quantity=1 WHERE uid=%s RETURNING *",
        (uid,),
    ).fetchone()


def normalize(db, character_id, *, uids=None):
    """Preserve original UIDs, options and full-bag remainders atomically.

    The caller owns the character write lock. Only ordinary inventory bags are
    used; a full inventory retains every unit in its original stack.
    """
    from .equipment import RULES
    from .inventory_uids import allocate

    items = list(
        db.execute(
            "SELECT * FROM inventory_items WHERE character_id=%s ORDER BY container,slot FOR UPDATE",
            (character_id,),
        )
    )
    occupied = {(row["container"], row["slot"]) for row in items}
    free = [
        (bag["uid"], slot)
        for bag in db.execute(
            "SELECT uid,capacity FROM inventory_containers WHERE character_id=%s "
            "AND kind BETWEEN 0 AND 3 ORDER BY kind",
            (character_id,),
        )
        for slot in range(bag["capacity"])
        if (bag["uid"], slot) not in occupied
    ]
    changed = []
    for item in items:
        if (
            (uids is not None and item["uid"] not in uids)
            or item["reference"] not in RULES
            or item["quantity"] <= 1
            or not free
        ):
            continue
        # Keep the original UID as the singleton. Existing build references,
        # bindings and socket state remain attached to that exact owned unit.
        remainder = item["quantity"] - 1
        while remainder and free:
            container, slot = free.pop(0)
            amount = 1 if free else remainder
            uid = allocate(db)
            db.execute(
                "INSERT INTO inventory_items(uid,character_id,reference,quantity,container,slot) "
                "VALUES(%s,%s,%s,%s,%s,%s)",
                (uid, character_id, item["reference"], amount, container, slot),
            )
            for table, columns in (
                ("inventory_item_elements", "damage_elements,resistance_elements"),
                ("inventory_item_bindings", "bound,template_reference"),
                ("inventory_item_recycling_state", "unidentified,socketed"),
                ("inventory_item_shards", "shard_state"),
            ):
                db.execute(
                    f"INSERT INTO {table}(uid,{columns}) SELECT %s,{columns} FROM {table} WHERE uid=%s",
                    (uid, item["uid"]),
                )
            remainder -= amount
        db.execute("UPDATE inventory_items SET quantity=1 WHERE uid=%s", (item["uid"],))
        changed.append(item["uid"])
    return changed


def for_sheet(db, character_id, blob):
    """Split only gear requested by an owned build, within its transaction."""
    from wakfu_server.wire import proto_fields

    uids = {
        dict(proto_fields(value)).get(8)
        for tag, value in proto_fields(blob)
        if tag == 10 and isinstance(value, bytes)
    }
    return normalize(db, character_id, uids=uids) if uids else []
