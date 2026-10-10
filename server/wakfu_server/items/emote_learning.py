"""Consume native bIw items once and persist account-owned emote knowledge."""
import struct
from wakfu_server.characters import emotes
from wakfu_server.wire import proto_fields


def learn(store, account_id, generation, character_id, body):
    if not isinstance(body, bytes) or len(body) != 12:
        raise ValueError("Emote learning requires twelve bytes")
    action_id, source_uid = struct.unpack(">iq", body)
    if action_id <= 0 or source_uid <= 0:
        raise ValueError("Invalid emote learning action or item UID")
    with store.connection() as db:
        db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account_id,))
        store.lock_character(db, account_id, generation, character_id)
        prior = db.execute(
            "SELECT * FROM emote_learning_receipts WHERE account_id=%s AND source_uid=%s",
            (account_id, source_uid),
        ).fetchone()
        if prior is not None:
            if prior["character_id"] != character_id or prior["action_id"] != action_id:
                raise ValueError("Emote learning replay does not match request")
            return {
                "character": store.character(account_id, character_id, db),
                "packets": [emotes.snapshot(db, account_id)],
                "applied": False,
            }
        item = db.execute(
            "SELECT * FROM inventory_items WHERE uid=%s AND character_id=%s FOR UPDATE",
            (source_uid, character_id),
        ).fetchone()
        if item is None or item["quantity"] < 1:
            raise ValueError("Emote learning item unavailable or foreign")
        rule = db.execute(
            "SELECT * FROM native_emote_learning_actions WHERE item_ref=%s",
            (item["reference"],),
        ).fetchone()
        from wakfu_server.haven_bag_furniture_knowledge import _rules

        native = _rules().get(item["reference"])
        if (
            rule is None
            or rule["action_id"] != action_id
            or rule["has_criteria"]
            or native is None
            or native.get("use_action_class") != "bIw"
            or native.get("use_action_id") != action_id
            or native.get("use_has_criteria") is not False
        ):
            raise ValueError("Unverified native emote learning action")
        if not db.execute(
            "SELECT 1 FROM native_emote_definitions WHERE emote_id=%s",
            (rule["emote_id"],),
        ).fetchone():
            raise ValueError("Emote definition is not verified")
        if db.execute(
            "SELECT 1 FROM account_emote_knowledge WHERE account_id=%s AND emote_id=%s",
            (account_id, rule["emote_id"]),
        ).fetchone():
            raise ValueError("Emote is already learned")
        character = store.character(account_id, character_id, db)
        for build in character.get("builds", {}).values():
            for tag, value in proto_fields(bytes.fromhex(build["equipment"])):
                if tag == 10 and dict(proto_fields(value)).get(8) == source_uid:
                    raise ValueError("Unequip the emote learning item first")
        for table in (
            "inventory_item_elements",
            "inventory_item_shards",
            "inventory_mounts",
        ):
            if db.execute(
                f"SELECT 1 FROM {table} WHERE uid=%s", (source_uid,)
            ).fetchone():
                raise ValueError("Unsupported emote learning item specific data")
        db.execute(
            "INSERT INTO account_emote_knowledge(account_id,emote_id) VALUES(%s,%s)",
            (account_id, rule["emote_id"]),
        )
        if item["quantity"] == 1:
            db.execute("DELETE FROM inventory_items WHERE uid=%s", (source_uid,))
        else:
            db.execute(
                "UPDATE inventory_items SET quantity=quantity-1 WHERE uid=%s",
                (source_uid,),
            )
        db.execute(
            "INSERT INTO emote_learning_receipts(account_id,source_uid,character_id,source_ref,action_id,emote_id) "
            "VALUES(%s,%s,%s,%s,%s,%s)",
            (
                account_id,
                source_uid,
                character_id,
                item["reference"],
                action_id,
                rule["emote_id"],
            ),
        )
        return {
            "character": store.character(account_id, character_id, db),
            "applied": True,
            "packets": [
                (12470, struct.pack(">qh", source_uid, -1)),
                (12266, struct.pack(">iB", rule["emote_id"], 1)),
                emotes.snapshot(db, account_id),
            ],
        }
