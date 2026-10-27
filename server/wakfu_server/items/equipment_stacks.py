"""Split equipment before native UI publication without losing owned units."""


class EquipmentOwnershipError(ValueError):
    """Keep native equipment rejection while explaining authorized custody."""

    def __init__(self, uid, *, owner_name=None):
        super().__init__("Equipment sheet item is unavailable or foreign")
        self.uid = uid
        self.owner_name = owner_name

    @property
    def player_message(self):
        if self.owner_name is not None:
            return (
                "No se puede guardar la build: un objeto está en el inventario de "
                f"{self.owner_name}. Si está equipado, quítalo de sus builds y "
                "guarda los cambios; después, desde el inventario normal de bolsas "
                "y fuera del editor de builds, transfiérelo al personaje que estás "
                "equipando y vuelve a guardar."
            )
        return (
            "No se puede guardar la build: un objeto ya no está disponible en el "
            "inventario de este personaje. Reabre el inventario y vuelve a "
            "seleccionar los objetos."
        )


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
        ("inventory_item_appearances", "appearance_ref"),
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
    """Repair identified legacy stacks without splitting unidentified equipment.

    The caller owns the character write lock. Ordinary native stacks remain
    intact until an action identifies or equips one unit.
    """
    from .equipment import RULES
    from .inventory_uids import allocate

    items = list(
        db.execute(
            "SELECT * FROM inventory_items WHERE character_id=%s ORDER BY container,slot FOR UPDATE",
            (character_id,),
        )
    )
    if uids is None:
        identities = [item["uid"] for item in items]
        uids = {
            row["uid"]
            for row in db.execute(
                "SELECT uid FROM inventory_item_shards WHERE uid=ANY(%s)",
                (identities,),
            )
        }
        uids.update(
            row["uid"]
            for row in db.execute(
                "SELECT uid FROM inventory_item_elements WHERE uid=ANY(%s) "
                "AND (damage_elements<>0 OR resistance_elements<>0)",
                (identities,),
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
                ("inventory_item_appearances", "appearance_ref"),
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
    if any(type(uid) is not int or uid <= 0 for uid in uids):
        raise ValueError("Invalid equipment sheet item UID")
    changed = []
    for uid in sorted(uids):
        item = db.execute(
            "SELECT quantity FROM inventory_items WHERE uid=%s AND character_id=%s",
            (uid, character_id),
        ).fetchone()
        if item is None:
            raise EquipmentOwnershipError(uid)
        if item["quantity"] > 1:
            ensure_singleton(db, character_id, uid)
            changed.append(uid)
    return changed
