"""Own account tutorial state; no captured tutorial progress is reused."""
import struct
from protocol_codec import Reader
from wakfu_server.wire import varint

# content.155.189 = "Entrar en tu merkalugar". The minimal local profile
# suppresses this introductory popup, without adding any character quest.
MINIMAL_DISCOVERED = (189,)


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
        if not db.execute(
            "SELECT 1 FROM sessions WHERE account_id=%s AND generation=%s AND expires_at>%s FOR UPDATE",
            (account_id, generation, store.now()),
        ).fetchone():
            raise ValueError("Stale tutorial session")
        for identity in ids:
            if add:
                db.execute(
                    "INSERT INTO account_tutorials VALUES(%s,%s,true) ON CONFLICT(account_id,tutorial_id) DO UPDATE SET pending=true",
                    (account_id, identity),
                )
            else:
                db.execute(
                    "UPDATE account_tutorials SET pending=false WHERE account_id=%s AND tutorial_id=%s",
                    (account_id, identity),
                )


def payload(store, account_id):
    with store.connection() as db:
        for identity in MINIMAL_DISCOVERED:
            db.execute(
                "INSERT INTO account_tutorials VALUES(%s,%s,false) ON CONFLICT(account_id,tutorial_id) DO NOTHING",
                (account_id, identity),
            )
        records = db.execute(
            "SELECT tutorial_id,pending FROM account_tutorials WHERE account_id=%s ORDER BY tutorial_id",
            (account_id,),
        ).fetchall()
    # Aa/ProtoTutorial: unpacked repeated int32 discovered=1, unread=2.
    proto = b"".join(b"\x08" + varint(r["tutorial_id"]) for r in records)
    proto += b"".join(
        b"\x10" + varint(r["tutorial_id"]) for r in records if r["pending"]
    )
    return struct.pack(">I", len(proto)) + proto
