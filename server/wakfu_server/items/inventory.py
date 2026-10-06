"""Owned empty containers, matching the native fresh-character bag layout.

Items and equipment mutations require their own authoritative codecs; empty
containers provide capacity without granting items from captured inventories.
"""
import struct


def initialize(db, character_id):
    """Initialize once under the owner lock; schemas belong to migrations."""
    if (
        db.execute(
            "SELECT id FROM characters WHERE id=%s FOR UPDATE", (character_id,)
        ).fetchone()
        is None
    ):
        raise ValueError("Invalid inventory owner")
    inserted = db.execute(
        "INSERT INTO inventory_initialized(character_id) VALUES(%s) "
        "ON CONFLICT(character_id) DO NOTHING RETURNING character_id",
        (character_id,),
    ).fetchone()
    if inserted is None:
        return
    for reference, kind, capacity in ((2175, 0, 30), (2603, 1, 4)):
        db.execute(
            "INSERT INTO inventory_containers(character_id,reference,kind,capacity,flags) "
            "VALUES(%s,%s,%s,%s,0)",
            (character_id, reference, kind, capacity),
        )


def load(db, character_id):
    return list(
        db.execute(
            "SELECT uid,character_id,reference,kind,capacity,flags FROM inventory_containers "
            "WHERE character_id=%s ORDER BY kind",
            (character_id,),
        )
    )


def bags(character):
    containers = character.get("inventory_containers")
    if containers is None:
        raise ValueError("Owned inventory containers must be loaded")
    if not 1 <= len(containers) <= 4:
        raise ValueError("Unsupported owned inventory container layout")
    if any(
        container.get("character_id") != character["id"] for container in containers
    ):
        raise ValueError("Foreign inventory container owner")
    base = containers[0]
    if (
        type(base["uid"]) is not int
        or not 0 < base["uid"] < (1 << 63)
        or any(
            base[key] != value
            for key, value in (
                ("reference", 2175),
                ("kind", 0),
                ("capacity", 30),
                ("flags", 0),
            )
        )
    ):
        raise ValueError("Invalid fixed base inventory container")
    from .inventory_bag_rules import ordinary

    slots = {0}
    uids = {containers[0]["uid"]}
    for item in containers[1:]:
        rule = ordinary(item["reference"])
        if (
            item["capacity"] != rule["capacity"]
            or item["flags"] != 0
            or item["kind"] not in (1, 2, 3)
            or item["uid"] <= 0
            or item["kind"] in slots
            or item["uid"] in uids
        ):
            raise ValueError("Invalid owned inventory bag layout")
        slots.add(item["kind"])
        uids.add(item["uid"])
    # oY/ti: u16 count, tg records, each with empty vF item/reserved-UID lists.
    from wakfu_server.inventory_items import item_form

    records = []
    remaining = list(character.get("inventory_items", []))
    for item in containers:
        contents = [entry for entry in remaining if entry["container"] == item["uid"]]
        slots = set()
        for entry in contents:
            if (
                entry["character_id"] != character["id"]
                or type(entry["slot"]) is not int
                or not 0 <= entry["slot"] < item["capacity"]
                or entry["slot"] in slots
            ):
                raise ValueError("Invalid owned item position")
            slots.add(entry["slot"])
            remaining.remove(entry)
        records.append(
            struct.pack(
                ">qiBhBH",
                item["uid"],
                item["reference"],
                item["kind"],
                item["capacity"],
                item["flags"],
                len(contents),
            )
            + b"".join(
                struct.pack(">h", entry["slot"]) + item_form(entry)
                for entry in contents
            )
            + b"\x00\x00"
        )
    if remaining:
        raise ValueError("Foreign or unavailable inventory container")
    return struct.pack(">H", len(containers)) + b"".join(records)
