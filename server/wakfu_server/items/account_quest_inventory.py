"""Owned native ACCOUNT_QUEST quantities, separate from projected artifacts."""
from .quest_inventory import _SOURCE

REFERENCES = frozenset(_SOURCE["account_quest_property_references"])


def validate(account_id, reference, quantity):
    if (
        type(account_id) is not int
        or account_id <= 0
        or type(reference) is not int
        or reference not in REFERENCES
        or type(quantity) is not int
        or not 1 <= quantity <= 32767
    ):
        raise ValueError("Invalid native account quest item")


def load(db, account_id):
    if type(account_id) is not int or account_id <= 0:
        raise ValueError("Invalid native account quest owner")
    rows = [
        dict(row)
        for row in db.execute(
            "SELECT account_id,reference,quantity FROM account_quest_items "
            "WHERE account_id=%s ORDER BY reference",
            (account_id,),
        )
    ]
    for row in rows:
        validate(row["account_id"], row["reference"], row["quantity"])
    return rows


def _lock(db, account_id):
    if (
        db.execute(
            "SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account_id,)
        ).fetchone()
        is None
    ):
        raise ValueError("Native account quest owner is unavailable")


def grant(db, account_id, reference, quantity):
    """Caller authorizes the owner; serialize grants with entrance debits."""
    validate(account_id, reference, quantity)
    _lock(db, account_id)
    old = db.execute(
        "SELECT quantity FROM account_quest_items WHERE account_id=%s AND reference=%s FOR UPDATE",
        (account_id, reference),
    ).fetchone()
    if (old["quantity"] if old else 0) + quantity > 32767:
        raise ValueError("Native account quest quantity capacity exceeded")
    return dict(
        db.execute(
            "INSERT INTO account_quest_items(account_id,reference,quantity) VALUES(%s,%s,%s) "
            "ON CONFLICT(account_id,reference) DO UPDATE SET "
            "quantity=account_quest_items.quantity+EXCLUDED.quantity RETURNING *",
            (account_id, reference, quantity),
        ).fetchone()
    )


def payment(db, account_id, reference, quantity, *, lock=False):
    """Read owned cost; projected exploration artifacts are never spendable."""
    validate(account_id, reference, quantity)
    if lock:
        _lock(db, account_id)
    row = db.execute(
        "SELECT account_id,reference,quantity FROM account_quest_items "
        "WHERE account_id=%s AND reference=%s" + (" FOR UPDATE" if lock else ""),
        (account_id, reference),
    ).fetchone()
    return None if row is None or row["quantity"] < quantity else dict(row)


def consume(db, account_id, reference, quantity):
    row = payment(db, account_id, reference, quantity, lock=True)
    if row is None:
        raise ValueError("Insufficient native account quest entrance item")
    if row["quantity"] == quantity:
        db.execute(
            "DELETE FROM account_quest_items WHERE account_id=%s AND reference=%s",
            (account_id, reference),
        )
    else:
        db.execute(
            "UPDATE account_quest_items SET quantity=quantity-%s WHERE account_id=%s AND reference=%s",
            (quantity, account_id, reference),
        )
    return dict(row, consumed=quantity)
