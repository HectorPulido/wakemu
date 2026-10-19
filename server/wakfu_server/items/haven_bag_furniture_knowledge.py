"""Account furniture learning from native bIx inventory actions.

Learning consumes one physical item once. Library placement and removal do
not transfer that learning item back into the inventory.
"""
import struct
from functools import lru_cache

from wakfu_server import native_catalog
from wakfu_server.paths import DATA_ROOT
from .inventory_items import _varint
from wakfu_server.wire import proto_fields


@lru_cache(maxsize=1)
def _rules():
    return {
        row["reference"]: row
        for row in native_catalog.load(DATA_ROOT / "item-action-rules.json")["items"]
    }


def _source_refs(source_ref, *, db, action_id):
    """Use bIx knowledge outputs, independent of portable placement templates."""
    row = db.execute(
        "SELECT learned_refs,has_criteria FROM native_furniture_learning_actions "
        "WHERE item_ref=%s AND action_id=%s",
        (source_ref, action_id),
    ).fetchone()
    if row is None or row["has_criteria"] is not False:
        return []
    refs = row["learned_refs"]
    if (
        not refs
        or len(set(refs)) != len(refs)
        or any(type(ref) is not int or not 0 < ref < 2**31 for ref in refs)
    ):
        raise ValueError("Invalid native furniture learning references")
    return sorted(refs)


def known(db, account_id, reference):
    return (
        db.execute(
            "SELECT 1 FROM account_furniture_knowledge WHERE account_id=%s AND item_ref=%s",
            (account_id, reference),
        ).fetchone()
        is not None
    )


def _snapshot(db, account_id):
    refs = [
        row["item_ref"]
        for row in db.execute(
            "SELECT item_ref FROM account_furniture_knowledge WHERE account_id=%s ORDER BY item_ref",
            (account_id,),
        )
    ]
    payload = b""
    for reference in refs:
        message = b"\x08" + _varint(reference)
        payload += b"\x0a" + _varint(len(message)) + message
    return 13873, struct.pack(">III", 1, 11, len(payload)) + payload


def packet(store, account_id):
    with store.connection() as db:
        return _snapshot(db, account_id)


def _learned(refs):
    return (
        13247,
        struct.pack(">I", len(refs))
        + b"".join(struct.pack(">I", reference) for reference in refs)
        + b"\x01",
    )


def learn(store, account_id, generation, character_id, body):
    """Validate cqd13220, consume once and persist account knowledge atomically."""
    if len(body) != 12:
        raise ValueError("Furniture learning requires exactly 12 request bytes")
    action_id, source_uid = struct.unpack(">iq", body)
    if action_id <= 0 or source_uid <= 0:
        raise ValueError("Invalid furniture learning action or item UID")
    with store.connection() as db:
        # Use account -> session -> owner order for shared collections.
        db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account_id,))
        from .inventory_owner import lock_inventory_character, lock_item_owner

        lock_inventory_character(store, db, account_id, generation, character_id)
        prior = db.execute(
            "SELECT * FROM furniture_learning_receipts WHERE account_id=%s AND source_uid=%s",
            (account_id, source_uid),
        ).fetchone()
        if prior is not None:
            character_id = lock_inventory_character(
                store, db, account_id, generation, prior["character_id"]
            )
            if prior["action_id"] != action_id:
                raise ValueError("Furniture learning receipt does not match request")
            return {
                "character": store.character(account_id, character_id, db),
                "packets": [_snapshot(db, account_id)],
                "applied": False,
            }
        character_id = lock_item_owner(
            store, db, account_id, generation, character_id, (source_uid,)
        )
        item = db.execute(
            "SELECT * FROM inventory_items WHERE uid=%s AND character_id=%s FOR UPDATE",
            (source_uid, character_id),
        ).fetchone()
        if item is None or item["quantity"] < 1:
            raise ValueError("Furniture learning item unavailable or foreign")
        rule = _rules().get(item["reference"])
        if (
            rule is None
            or rule.get("use_action_class") != "bIx"
            or rule.get("use_action_id") != action_id
            or rule.get("use_has_criteria") is not False
        ):
            raise ValueError("Furniture learning action or native criteria unsupported")
        refs = _source_refs(item["reference"], db=db, action_id=action_id)
        if not refs:
            raise ValueError("Furniture learning source has no native learning mapping")
        character = store.character(account_id, character_id, db)
        for build in character.get("builds", {}).values():
            for tag, value in proto_fields(bytes.fromhex(build["equipment"])):
                if tag == 10 and dict(proto_fields(value)).get(8) == source_uid:
                    raise ValueError("Unequip the learning item before use")
        for table in (
            "inventory_item_elements",
            "inventory_item_shards",
            "inventory_mounts",
        ):
            if db.execute(
                f"SELECT 1 FROM {table} WHERE uid=%s", (source_uid,)
            ).fetchone():
                raise ValueError(
                    "Furniture learning item has unsupported specific data"
                )
        added = [
            reference for reference in refs if not known(db, account_id, reference)
        ]
        if not added:
            raise ValueError("Furniture is already learned")
        for reference in added:
            db.execute(
                "INSERT INTO account_furniture_knowledge(account_id,item_ref) VALUES(%s,%s)",
                (account_id, reference),
            )
        if item["quantity"] == 1:
            db.execute("DELETE FROM inventory_items WHERE uid=%s", (source_uid,))
        else:
            db.execute(
                "UPDATE inventory_items SET quantity=quantity-1 WHERE uid=%s",
                (source_uid,),
            )
        db.execute(
            "INSERT INTO furniture_learning_receipts(account_id,source_uid,character_id,source_ref,action_id,learned_refs) "
            "VALUES(%s,%s,%s,%s,%s,%s)",
            (account_id, source_uid, character_id, item["reference"], action_id, added),
        )
        return {
            "character": store.character(account_id, character_id, db),
            "packets": [
                (12470, struct.pack(">qh", source_uid, -1)),
                _snapshot(db, account_id),
                _learned(added),
            ],
            "applied": True,
        }
