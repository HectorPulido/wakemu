"""Own account tutorial state; no captured tutorial progress is reused."""
import struct
from protocol_codec import Reader
from wakfu_server.wire import varint

# content.155.189 = "Entrar en tu merkalugar". The minimal local profile
# suppresses this introductory popup, without adding any character quest.
MINIMAL_DISCOVERED = (189,)


def schema(db):
    db.execute(
        "CREATE TABLE IF NOT EXISTS account_tutorials (account_id INTEGER NOT NULL REFERENCES accounts(id), tutorial_id INTEGER NOT NULL, pending INTEGER NOT NULL CHECK(pending IN (0,1)), PRIMARY KEY(account_id,tutorial_id))"
    )


def decode(body):
    r = Reader(body)
    add = r.number("B")
    count = r.number("I")
    if add not in (0, 1) or count > 1024:
        raise ValueError("Invalid tutorial update")
    ids = {r.number("i") for _ in range(count)}
    r.finish()
    if any(i < 0 for i in ids):
        raise ValueError("Invalid tutorial identity")
    return bool(add), ids


def update(store, account_id, generation, body):
    add, ids = decode(body)
    with store.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        if not db.execute(
            "SELECT 1 FROM sessions WHERE account_id=? AND generation=? AND expires_at>?",
            (account_id, generation, store.clock()),
        ).fetchone():
            raise ValueError("Stale tutorial session")
        for identity in ids:
            if add:
                db.execute(
                    "INSERT INTO account_tutorials VALUES(?,?,1) ON CONFLICT(account_id,tutorial_id) DO UPDATE SET pending=1",
                    (account_id, identity),
                )
            else:
                db.execute(
                    "UPDATE account_tutorials SET pending=0 WHERE account_id=? AND tutorial_id=?",
                    (account_id, identity),
                )


def payload(store, account_id):
    with store.connection() as db:
        for identity in MINIMAL_DISCOVERED:
            db.execute(
                "INSERT OR IGNORE INTO account_tutorials VALUES(?,?,0)",
                (account_id, identity),
            )
        records = db.execute(
            "SELECT tutorial_id,pending FROM account_tutorials WHERE account_id=? ORDER BY tutorial_id",
            (account_id,),
        ).fetchall()
    # Aa/ProtoTutorial: unpacked repeated int32 discovered=1, unread=2.
    proto = b"".join(b"\x08" + varint(r["tutorial_id"]) for r in records)
    proto += b"".join(
        b"\x10" + varint(r["tutorial_id"]) for r in records if r["pending"]
    )
    return struct.pack(">I", len(proto)) + proto
