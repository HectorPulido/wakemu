"""Per-UID mutable state while a physical item is a bag or placed furniture."""
from psycopg.types.json import Jsonb

from . import item_custody_metadata


def _json(value):
    if isinstance(value, (bytes, bytearray, memoryview)):
        return {"$bytes": bytes(value).hex()}
    if isinstance(value, dict):
        return {key: _json(entry) for key, entry in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json(entry) for entry in value]
    return value


def _unjson(value):
    if isinstance(value, dict):
        if set(value) == {"$bytes"}:
            return bytes.fromhex(value["$bytes"])
        return {key: _unjson(entry) for key, entry in value.items()}
    if isinstance(value, list):
        return [_unjson(entry) for entry in value]
    return value


def hold(db, item, *, uid, account_id, kind):
    """Snapshot before inventory deletion/splitting in the caller transaction."""
    metadata = item_custody_metadata.clone(
        item_custody_metadata.snapshot(db, item["uid"]),
        uid,
    )
    db.execute(
        "INSERT INTO portable_item_custody"
        "(uid,account_id,source_character_id,reference,kind,metadata) VALUES(%s,%s,%s,%s,%s,%s)",
        (
            uid,
            account_id,
            item["character_id"],
            item["reference"],
            kind,
            Jsonb(_json(metadata)),
        ),
    )


def restore(db, *, uid, account_id, character_id, reference, kind):
    """Restore exact metadata after the caller has recreated the inventory row."""
    row = db.execute(
        "SELECT * FROM portable_item_custody WHERE uid=%s FOR UPDATE",
        (uid,),
    ).fetchone()
    if row is None:
        # Existing deployed furniture and initial equipped bags predate custody.
        return
    if (row["account_id"], row["reference"], row["kind"]) != (
        account_id,
        reference,
        kind,
    ):
        raise ValueError("Foreign portable item custody")
    metadata = _unjson(row["metadata"])
    binding = metadata.get("inventory_item_bindings", {})
    if row["source_character_id"] != character_id:
        from .item_binding import _template

        native_binding = _template(reference)[0]
        if native_binding == "BOUND_ON_PICKUP_TO_CHARACTER" or (
            binding.get("bound") is True
            and native_binding != "BOUND_ON_PICKUP_TO_ACCOUNT"
        ):
            raise ValueError("Portable item is bound to another character")
    for table, entry in metadata.items():
        item_custody_metadata._validate(table, entry)
        if entry[item_custody_metadata.TABLE_KEYS[table]] != uid:
            raise ValueError("Foreign portable metadata identity")
    item_custody_metadata.restore(db, metadata)
    db.execute("DELETE FROM portable_item_custody WHERE uid=%s", (uid,))
