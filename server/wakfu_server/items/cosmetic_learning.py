"""Native bIt account cosmetic acquisition, separate from furniture bIx learning."""
import struct
from psycopg.types.json import Jsonb
from wakfu_server.characters.cosmetics import OwnedCosmetics
from wakfu_server.characters.cosmetic_store import load
from wakfu_server.wire import proto_fields


def snapshot(record):
    return (
        13873,
        struct.pack(">II", 2, 8)
        + record.inventory_component()
        + struct.pack(">I", 9)
        + record.preset_component(),
    )


def learn(store, account_id, generation, character_id, body, *, kind="cosmetic"):
    if kind not in ("cosmetic", "title"):
        raise ValueError("Unsupported account learning kind")
    receipt_table = (
        "title_learning_receipts" if kind == "title" else "cosmetic_learning_receipts"
    )
    action_table = (
        "native_title_learning_actions"
        if kind == "title"
        else "native_cosmetic_learning_actions"
    )
    native_class = "bIs" if kind == "title" else "bIt"
    if not isinstance(body, bytes) or len(body) != 12:
        raise ValueError("Item learning requires exactly 12 request bytes")
    action_id, source_uid = struct.unpack(">iq", body)
    if action_id <= 0 or source_uid <= 0:
        raise ValueError("Invalid cosmetic learning action or item UID")
    with store.connection() as db:
        # Account cosmetics are shared; use the same lock order as preset writers.
        db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account_id,))
        from .inventory_owner import lock_inventory_character, lock_item_owner

        lock_inventory_character(store, db, account_id, generation, character_id)
        prior = db.execute(
            f"SELECT * FROM {receipt_table} WHERE account_id=%s AND source_uid=%s",
            (account_id, source_uid),
        ).fetchone()
        if prior is not None:
            character_id = lock_inventory_character(
                store, db, account_id, generation, prior["character_id"]
            )
            if prior["action_id"] != action_id:
                raise ValueError("Cosmetic learning receipt does not match request")
            record = load(db, account_id)
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
            raise ValueError("Cosmetic learning item unavailable or foreign")
        rule = db.execute(
            f"SELECT * FROM {action_table} WHERE item_ref=%s",
            (item["reference"],),
        ).fetchone()
        if rule is None or rule["action_id"] != action_id or rule["has_criteria"]:
            raise ValueError("Unsupported cosmetic learning action or native criteria")
        from wakfu_server.haven_bag_furniture_knowledge import _rules

        active = _rules().get(item["reference"])
        if (
            active is None
            or active.get("use_action_class") != native_class
            or active.get("use_action_id") != action_id
            # The legacy published flag includes EXCHANGE criteria. Titles use
            # the action's native USE criterion from the authoritative table.
            or (kind != "title" and active.get("use_has_criteria") is not False)
        ):
            raise ValueError(
                "Cosmetic action does not match the published native catalog"
            )
        record = load(db, account_id)
        if record is None:
            raise ValueError("Missing account cosmetic schema")
        owned = (
            (7, rule["title_id"], 0, 0)
            if kind == "title"
            else (rule["category"], item["reference"], 0, 0)
        )
        if any(row[:2] == owned[:2] for row in record.items):
            raise ValueError("Cosmetic is already learned")
        character = store.character(account_id, character_id, db)
        for build in character.get("builds", {}).values():
            for tag, value in proto_fields(bytes.fromhex(build["equipment"])):
                if tag == 10 and dict(proto_fields(value)).get(8) == source_uid:
                    raise ValueError("Unequip the learning item before use")
        for table in (
            "inventory_item_elements",
            "inventory_item_shards",
            "inventory_mounts",
            "inventory_pets",
        ):
            if db.execute(
                f"SELECT 1 FROM {table} WHERE uid=%s", (source_uid,)
            ).fetchone():
                raise ValueError("Cosmetic learning item has unsupported specific data")
        record = OwnedCosmetics(
            record.account_id,
            record.items + (owned,),
            record.selections,
            record.inactive_characters,
            record.costumes,
            record.single_selections,
        )
        # Provide the existing native preset UI a character-owned selection target.
        if character_id not in dict(record.selections):
            record = record.equip_finishers(character, ())
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
        result_column = "title_id" if kind == "title" else "category"
        result_value = rule[result_column]
        db.execute(
            f"INSERT INTO {receipt_table}(account_id,source_uid,character_id,source_ref,action_id,{result_column}) "
            "VALUES(%s,%s,%s,%s,%s,%s)",
            (
                account_id,
                source_uid,
                character_id,
                item["reference"],
                action_id,
                result_value,
            ),
        )
        return {
            "character": store.character(account_id, character_id, db),
            "packets": [(12470, struct.pack(">qh", source_uid, -1)), snapshot(record)],
            "applied": True,
        }


LEARNING_ACTION_CLASSES = frozenset(
    (
        "bHv",
        "bIA",
        "bIB",
        "bIs",
        "bIt",
        "bIv",
        "bIw",
        "bIx",
        "bIz",
    )
)


def request_action_class(body):
    """Classify original cqd13220 by its native action and exact suffix grammar.

    bHv appends a selected equipment UID. The other eight learning classes
    append nothing; bIi alone uses the existing planting coordinate suffix.
    Neither unknown actions nor malformed learning requests enter planting.
    """
    if not isinstance(body, bytes) or len(body) not in (12, 20):
        raise ValueError("Invalid native item action request size")
    action_id, source_uid = struct.unpack_from(">iq", body)
    if action_id <= 0 or source_uid <= 0:
        raise ValueError("Invalid native item action or source UID")
    from wakfu_server.haven_bag_furniture_knowledge import _rules

    classes = {
        row.get("use_action_class")
        for row in _rules().values()
        if row.get("use_action_id") == action_id
    }
    if len(classes) != 1:
        raise ValueError("Unknown or ambiguous native item action")
    native_class = classes.pop()
    if native_class not in LEARNING_ACTION_CLASSES and native_class != "bIi":
        raise ValueError("Unsupported native inventory action")
    expected_size = 20 if native_class in ("bHv", "bIi") else 12
    if len(body) != expected_size:
        raise ValueError("Native item action request suffix does not match its class")
    if native_class == "bHv" and struct.unpack_from(">q", body, 12)[0] <= 0:
        raise ValueError("Invalid native mimic target UID")
    return native_class


def learn_item(store, account_id, generation, character_id, body):
    """Dispatch cqd13220 by native class; each domain owns custody and replay.

    The immutable action class is available even after consumption. Domain
    handlers still lock the current lease/actual item or its account receipt,
    so classification grants neither inventory ownership nor knowledge.
    """
    native_class = request_action_class(body)
    if native_class == "bIi":
        raise ValueError("Planting requires its native location authority")
    if native_class in ("bIs", "bIt"):
        return learn(
            store,
            account_id,
            generation,
            character_id,
            body,
            kind="title" if native_class == "bIs" else "cosmetic",
        )
    from importlib import import_module

    module = {
        "bHv": "mimisymbic_learning",
        "bIA": "haven_ranch_building_knowledge",
        "bIB": "recipe_learning",
        "bIv": "haven_bag_view_learning",
        "bIw": "emote_learning",
        "bIx": "haven_bag_furniture_knowledge",
        "bIz": "recipe_learning",
    }[native_class]
    handler = import_module("wakfu_server." + module).learn
    return handler(store, account_id, generation, character_id, body)
