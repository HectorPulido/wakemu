"""Persistent item UID allocation and lease-scoped native client split pool."""
import struct


def schema(db):
    db.execute(
        "CREATE TABLE IF NOT EXISTS inventory_uid_sequence (singleton INTEGER PRIMARY KEY CHECK(singleton=1), last_uid INTEGER NOT NULL)"
    )
    highest = db.execute("SELECT coalesce(max(uid),0) FROM inventory_items").fetchone()[
        0
    ]
    db.execute(
        "INSERT OR IGNORE INTO inventory_uid_sequence VALUES(1,?)",
        (max(1 << 40, highest),),
    )
    db.execute(
        """CREATE TABLE IF NOT EXISTS inventory_reserved_uids (
        uid INTEGER PRIMARY KEY, account_id INTEGER NOT NULL, generation TEXT NOT NULL,
        character_id INTEGER NOT NULL, used_request BLOB)"""
    )


def allocate(db):
    schema(db)
    value = (
        db.execute(
            "SELECT last_uid FROM inventory_uid_sequence WHERE singleton=1"
        ).fetchone()[0]
        + 1
    )
    if value >= (1 << 63):
        raise ValueError("Item UID range exhausted")
    db.execute(
        "UPDATE inventory_uid_sequence SET last_uid=? WHERE singleton=1", (value,)
    )
    return value


def _reserve(store, account_id, generation, character_id, *, count=32, reset=False):
    if type(count) is not int or not 1 <= count <= 127:
        raise ValueError("Invalid native UID pool size")
    from .inventory_items import _lease

    with store.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        _lease(store, db, account_id, generation, character_id)
        schema(db)
        if reset:
            # bGE is a client-wide pool. Character selection clears all unused
            # reservations in this lease, while consumed request replay stays valid.
            db.execute(
                "DELETE FROM inventory_reserved_uids WHERE account_id=? AND generation=? AND used_request IS NULL",
                (account_id, generation),
            )
        # Replenishment quota prevents unbounded client-reserved state.
        outstanding = db.execute(
            "SELECT count(*) FROM inventory_reserved_uids WHERE account_id=? AND generation=? AND character_id=? AND used_request IS NULL",
            (account_id, generation, character_id),
        ).fetchone()[0]
        if outstanding + count > 127:
            raise ValueError("Client UID reservation quota exceeded")
        values = []
        for _ in range(count):
            uid = allocate(db)
            values.append(uid)
            db.execute(
                "INSERT INTO inventory_reserved_uids VALUES(?,?,?,?,NULL)",
                (uid, account_id, generation, character_id),
            )
        # cwX: mode0 clears client pool; nonzero appends, then signedbytecount.
        return dict(
            uids=values,
            packet=(
                13778,
                struct.pack(">bb", 0 if reset else 1, count)
                + b"".join(struct.pack(">q", uid) for uid in values),
            ),
        )


def reserve(store, account_id, generation, character_id, *, count=32):
    return _reserve(store, account_id, generation, character_id, count=count)


def initialize_pool(store, account_id, generation, character_id, *, count=32):
    """Replace unused lease reservations and clear the native client pool."""
    return _reserve(
        store, account_id, generation, character_id, count=count, reset=True
    )


def replenish(store, account_id, generation, character_id, body, *, count=32):
    """Native cpQ13589: own character q, UID allocator selector i=0."""
    if len(body) != 12:
        raise ValueError("Invalid UID replenish request length")
    requested_character, mode = struct.unpack(">qi", body)
    if requested_character != character_id or mode != 0:
        raise ValueError("Invalid UID replenish request owner or selector")
    return reserve(store, account_id, generation, character_id, count=count)
