"""Owned empty containers, matching the native fresh-character bag layout.

Items and equipment mutations require their own authoritative codecs; empty
containers provide capacity without granting items from captured inventories.
"""
import struct


def initial_containers(character_id):
    if type(character_id) is not int or not 0 < character_id < (1 << 55):
        raise ValueError("Invalid inventory owner")
    return [
        dict(
            uid=character_id * 256 + 128, reference=2175, kind=0, capacity=30, flags=0
        ),
        dict(uid=character_id * 256 + 129, reference=2603, kind=1, capacity=4, flags=0),
    ]


def load(db, character_id):
    db.execute(
        """CREATE TABLE IF NOT EXISTS inventory_containers (
        character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
        uid INTEGER NOT NULL UNIQUE, reference INTEGER NOT NULL,
        kind INTEGER NOT NULL, capacity INTEGER NOT NULL, flags INTEGER NOT NULL,
        PRIMARY KEY(character_id,kind))"""
    )
    db.execute(
        """CREATE TABLE IF NOT EXISTS inventory_initialized (
        character_id INTEGER PRIMARY KEY REFERENCES characters(id) ON DELETE CASCADE)"""
    )
    if (
        db.execute(
            "SELECT 1 FROM inventory_initialized WHERE character_id=?", (character_id,)
        ).fetchone()
        is None
    ):
        if (
            db.execute(
                "SELECT 1 FROM inventory_containers WHERE character_id=?",
                (character_id,),
            ).fetchone()
            is None
        ):
            for container in initial_containers(character_id):
                db.execute(
                    """INSERT INTO inventory_containers
                    (character_id,uid,reference,kind,capacity,flags) VALUES(?,?,?,?,?,?)""",
                    (
                        character_id,
                        *(
                            container[key]
                            for key in ("uid", "reference", "kind", "capacity", "flags")
                        ),
                    ),
                )
        db.execute("INSERT INTO inventory_initialized VALUES(?)", (character_id,))
    return [
        dict(row)
        for row in db.execute(
            """SELECT uid,reference,kind,capacity,flags
        FROM inventory_containers WHERE character_id=? ORDER BY kind""",
            (character_id,),
        )
    ]


def bags(character):
    containers = character.get("inventory_containers")
    if containers is None:
        containers = initial_containers(character["id"])
    if not 1 <= len(containers) <= 4:
        raise ValueError("Unsupported owned inventory container layout")
    expected = initial_containers(character["id"])
    if containers[0] != expected[0]:
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
