"""Persistent item UID allocation and lease-scoped native client split pool."""
import struct


def allocate(db):
    """Sequence allocation is shared and never reused after rollback."""
    return db.execute("SELECT nextval('inventory_uid') AS uid").fetchone()["uid"]


def _reserve(store, account_id, generation, character_id, *, count=32, reset=False):
    if type(count) is not int or not 1 <= count <= 127:
        raise ValueError("Invalid native UID pool size")
    with store.connection() as db:
        # Serialize reservations for a lease before checking its quota.
        session = db.execute(
            "SELECT character_id FROM sessions WHERE account_id=%s AND generation=%s "
            "AND expires_at>%s FOR UPDATE",
            (account_id, generation, store.now()),
        ).fetchone()
        if session is None or session["character_id"] != character_id:
            raise ValueError("Invalid inventory session")
        if reset:
            # bGE is a client-wide pool. Character selection clears all unused
            # reservations in this lease, while consumed request replay stays valid.
            db.execute(
                "DELETE FROM inventory_reserved_uids WHERE account_id=%s AND generation=%s AND used_request IS NULL",
                (account_id, generation),
            )
        # Replenishment quota prevents unbounded client-reserved state.
        outstanding = db.execute(
            "SELECT count(*) AS outstanding FROM inventory_reserved_uids WHERE account_id=%s AND generation=%s AND character_id=%s AND used_request IS NULL",
            (account_id, generation, character_id),
        ).fetchone()["outstanding"]
        if outstanding + count > 127:
            raise ValueError("Client UID reservation quota exceeded")
        values = []
        for _ in range(count):
            uid = allocate(db)
            values.append(uid)
            db.execute(
                "INSERT INTO inventory_reserved_uids(uid,account_id,generation,character_id,used_request) VALUES(%s,%s,%s,%s,NULL)",
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
