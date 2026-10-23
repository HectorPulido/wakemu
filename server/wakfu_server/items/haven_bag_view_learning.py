"""Native bIv Haven Bag skin acquisition in account cosmetic category 15.

The owned reference is the action's view ID, never its physical source item.
Learning changes knowledge only; selecting the bag exterior is a separate action.
"""
import struct

from psycopg.types.json import Jsonb

from wakfu_server.cosmetic_learning import snapshot
from wakfu_server.characters.cosmetic_store import load
from wakfu_server.characters.cosmetics import OwnedCosmetics
from wakfu_server.inventory_owner import lock_inventory_character, lock_item_owner
from wakfu_server.wire import proto_fields


def learn(store, account_id, generation, character_id, body):
    """Consume one authenticated source once and publish durable skin knowledge."""
    if not isinstance(body, bytes) or len(body) != 12:
        raise ValueError("Bag view learning requires exactly 12 request bytes")
    action_id, source_uid = struct.unpack(">iq", body)
    if action_id <= 0 or source_uid <= 0:
        raise ValueError("Invalid bag view learning action or item UID")
    with store.connection() as db:
        db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account_id,))
        lock_inventory_character(store, db, account_id, generation, character_id)
        prior = db.execute(
            "SELECT * FROM bag_view_learning_receipts WHERE account_id=%s AND source_uid=%s",
            (account_id, source_uid),
        ).fetchone()
        if prior is not None:
            character_id = lock_inventory_character(
                store, db, account_id, generation, prior["character_id"]
            )
            if prior["action_id"] != action_id:
                raise ValueError("Bag view learning receipt does not match request")
            record = load(db, account_id)
            if record is None or not any(
                row[:2] == (15, prior["view_id"]) for row in record.items
            ):
                raise ValueError("Missing committed bag view knowledge")
            return {
                "character": store.character(account_id, character_id, db),
                "packets": [snapshot(record)],
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
            raise ValueError("Bag view learning item unavailable or foreign")
        rule = db.execute(
            "SELECT * FROM native_bag_view_learning_actions WHERE item_ref=%s",
            (item["reference"],),
        ).fetchone()
        from wakfu_server.haven_bag_furniture_knowledge import _rules

        active = _rules().get(item["reference"])
        if (
            rule is None
            or rule["action_id"] != action_id
            or rule["has_criteria"] is not False
            or type(rule["view_id"]) is not int
            or rule["view_id"] <= 0
            or active is None
            or active.get("use_action_class") != "bIv"
            or active.get("use_action_id") != action_id
            or active.get("use_has_criteria") is not False
        ):
            raise ValueError("Unverified native bag view learning action")
        record = load(db, account_id)
        if record is None:
            raise ValueError("Missing account cosmetic schema")
        owned = (15, rule["view_id"], 0, 0)
        if any(row[:2] == owned[:2] for row in record.items):
            raise ValueError("Bag view is already learned")
        character = store.character(account_id, character_id, db)
        for build in character.get("builds", {}).values():
            for tag, value in proto_fields(bytes.fromhex(build["equipment"])):
                if tag == 10 and dict(proto_fields(value)).get(8) == source_uid:
                    raise ValueError("Unequip the bag view learning item first")
        for table in (
            "inventory_item_elements",
            "inventory_item_shards",
            "inventory_mounts",
            "inventory_pets",
        ):
            if db.execute(
                f"SELECT 1 FROM {table} WHERE uid=%s", (source_uid,)
            ).fetchone():
                raise ValueError("Bag view learning item has unsupported specific data")
        record = OwnedCosmetics(
            record.account_id,
            record.items + (owned,),
            record.selections,
            record.inactive_characters,
            record.costumes,
            record.single_selections,
        )
        db.execute(
            "INSERT INTO account_cosmetics(account_id,record) VALUES(%s,%s) "
            "ON CONFLICT(account_id) DO UPDATE SET record=EXCLUDED.record,revision=account_cosmetics.revision+1",
            (account_id, Jsonb(record.to_record())),
        )
        if item["quantity"] == 1:
            db.execute("DELETE FROM inventory_items WHERE uid=%s", (source_uid,))
        else:
            db.execute(
                "UPDATE inventory_items SET quantity=quantity-1 WHERE uid=%s",
                (source_uid,),
            )
        db.execute(
            "INSERT INTO bag_view_learning_receipts(account_id,source_uid,character_id,source_ref,action_id,view_id) "
            "VALUES(%s,%s,%s,%s,%s,%s)",
            (
                account_id,
                source_uid,
                character_id,
                item["reference"],
                action_id,
                rule["view_id"],
            ),
        )
        return {
            "character": store.character(account_id, character_id, db),
            "packets": [(12470, struct.pack(">qh", source_uid, -1)), snapshot(record)],
            "applied": True,
        }
