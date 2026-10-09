"""Owned cosmetic persistence; equip never creates account ownership."""
from psycopg.types.json import Jsonb
from .cosmetics import OwnedCosmetics


def load(db, account_id):
    schema = db.execute(
        "SELECT to_regclass('public.account_cosmetics') AS relation"
    ).fetchone()
    if schema is None or schema["relation"] is None:
        return None
    row = db.execute(
        "SELECT record FROM account_cosmetics WHERE account_id=%s", (account_id,)
    ).fetchone()
    return (
        OwnedCosmetics(account_id, ())
        if row is None
        else OwnedCosmetics.from_record(row["record"], account_id=account_id)
    )


def equip_finishers(db, character, references, *, updated_record=None):
    # All cosmetic writers acquire account before character.
    db.execute(
        "SELECT id FROM accounts WHERE id=%s FOR UPDATE", (character["account_id"],)
    )
    owner = db.execute(
        "SELECT id FROM characters WHERE id=%s AND account_id=%s AND deleted_at IS NULL FOR UPDATE",
        (character["id"], character["account_id"]),
    ).fetchone()
    if owner is None:
        raise ValueError("Missing owned cosmetic character")
    record = load(db, character["account_id"])
    if record is None:
        raise ValueError("Missing account cosmetic schema")
    # Preserve all account-owned rows; selection changes cannot grant items.
    if updated_record is None:
        record = record.equip_finishers(character, references)
    else:
        if (
            not isinstance(updated_record, OwnedCosmetics)
            or updated_record.account_id != record.account_id
            or updated_record.items != record.items
        ):
            raise ValueError("Cosmetic update cannot change ownership")
        record = updated_record
    db.execute(
        "INSERT INTO account_cosmetics(account_id,record) VALUES(%s,%s) ON CONFLICT(account_id) DO UPDATE SET record=EXCLUDED.record,revision=account_cosmetics.revision+1",
        (record.account_id, Jsonb(record.to_record())),
    )
    return record
