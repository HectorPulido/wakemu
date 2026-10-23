"""Native bHv account-owned accessory appearance learning."""
import struct

from psycopg.types.json import Jsonb

from .cosmetic_learning import snapshot
from wakfu_server.characters.cosmetic_store import load
from wakfu_server.characters.cosmetics import OwnedCosmetics
from .inventory_owner import lock_inventory_character, lock_item_owner
from wakfu_server.wire import proto_fields


CLIENT_SHA256 = "e3eb8b9b6a1fa0d42d2f06f0af3e841ed783b2998f5c81d3cd8312294106d3cd"
SOURCE_REF = 31508
ACTION_ID = 13882
ELIGIBLE_CATEGORIES = frozenset(range(8, 15))


def _request(body):
    if not isinstance(body, bytes) or len(body) != 20:
        raise ValueError("Mimisymbic learning requires exactly 20 request bytes")
    action_id, source_uid, target_uid = struct.unpack(">iqq", body)
    if (
        action_id != ACTION_ID
        or source_uid <= 0
        or target_uid <= 0
        or source_uid == target_uid
    ):
        raise ValueError("Invalid native mimisymbic action or item UID")
    return source_uid, target_uid


def _validate_source_rule(db, item):
    rule = db.execute(
        "SELECT * FROM native_mimisymbic_learning_actions WHERE item_ref=%s",
        (item["reference"],),
    ).fetchone()
    if (
        rule is None
        or rule["item_ref"] != SOURCE_REF
        or rule["action_id"] != ACTION_ID
        or rule["native_class"] != "bHv"
        or rule["has_criteria"] is not False
        or rule["source_sha256"] != CLIENT_SHA256
        or item["reference"] != SOURCE_REF
    ):
        raise ValueError("Unsupported native mimisymbic action")

    from .haven_bag_furniture_knowledge import _rules

    active = _rules().get(SOURCE_REF)
    if (
        active is None
        or active.get("use_action_class") != "bHv"
        or active.get("use_action_id") != ACTION_ID
        or active.get("use_has_criteria") is not False
    ):
        raise ValueError("Mimisymbic action differs from the published native catalog")


def _target_definition(db, target_ref):
    rows = list(
        db.execute(
            "SELECT target_ref,appearance_ref,category,source_sha256 "
            "FROM native_mimisymbic_targets WHERE target_ref=%s ORDER BY category",
            (target_ref,),
        )
    )
    if not rows:
        raise ValueError("Target is not a verified native accessory appearance")
    first = rows[0]
    categories = tuple(row["category"] for row in rows)
    if (
        first["target_ref"] != target_ref
        or type(first["appearance_ref"]) is not int
        or first["appearance_ref"] <= 0
        or not categories
        or len(set(categories)) != len(categories)
        or any(category not in ELIGIBLE_CATEGORIES for category in categories)
        or any(
            row["target_ref"] != target_ref
            or row["appearance_ref"] != first["appearance_ref"]
            or row["source_sha256"] != CLIENT_SHA256
            for row in rows
        )
    ):
        raise ValueError("Target is not a verified native accessory appearance")
    return {"appearance_ref": first["appearance_ref"], "categories": categories}


def _is_equipped(character, uid):
    for build in character.get("builds", {}).values():
        for tag, value in proto_fields(bytes.fromhex(build["equipment"])):
            if tag == 10 and dict(proto_fields(value)).get(8) == uid:
                return True
    return False


def _has_specific_data(db, uid):
    for table in (
        "inventory_item_elements",
        "inventory_item_shards",
        "inventory_mounts",
        "inventory_pets",
    ):
        if db.execute(f"SELECT 1 FROM {table} WHERE uid=%s", (uid,)).fetchone():
            return True
    return False


def _result(store, db, account_id, character_id, record, *, applied, source_uid=None):
    packets = []
    if applied:
        packets.append((12470, struct.pack(">qh", source_uid, -1)))
    packets.append(snapshot(record))
    return {
        "character": store.character(account_id, character_id, db),
        "packets": packets,
        "applied": applied,
    }


def learn(store, account_id, generation, character_id, body):
    """Consume bHv once and persist the selected accessory as account knowledge.

    The target descriptor is generated from original-client appearance metadata;
    unknown target references fail closed. The target instance is never consumed.
    """
    source_uid, target_uid = _request(body)
    with store.connection() as db:
        db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account_id,))
        lock_inventory_character(store, db, account_id, generation, character_id)

        prior = db.execute(
            "SELECT * FROM mimisymbic_learning_receipts "
            "WHERE account_id=%s AND source_uid=%s FOR UPDATE",
            (account_id, source_uid),
        ).fetchone()
        if prior is not None:
            # Original bJd.aW resolves an existing per-unit skin before its
            # statistical template. A replay retains that learned appearance,
            # even if the physical target has subsequently changed appearance.
            definition = _target_definition(db, prior["appearance_ref"])
            if (
                prior["action_id"] != ACTION_ID
                or prior["source_ref"] != SOURCE_REF
                or prior["target_uid"] != target_uid
                or tuple(prior["categories"]) != definition["categories"]
                or prior["appearance_ref"] != definition["appearance_ref"]
            ):
                raise ValueError("Mimisymbic receipt does not match request")
            owner_id = lock_inventory_character(
                store, db, account_id, generation, prior["character_id"]
            )
            record = load(db, account_id)
            owned_keys = set() if record is None else {row[:2] for row in record.items}
            if record is None or not all(
                (category, prior["appearance_ref"]) in owned_keys
                for category in definition["categories"]
            ):
                raise ValueError("Missing committed mimisymbic appearance")
            return _result(store, db, account_id, owner_id, record, applied=False)

        owner_id = lock_item_owner(
            store, db, account_id, generation, character_id, (source_uid,)
        )
        # Lock both instances in stable UID order before checking either owner.
        rows = list(
            db.execute(
                "SELECT * FROM inventory_items WHERE uid=ANY(%s) "
                "ORDER BY uid FOR UPDATE",
                ([source_uid, target_uid],),
            )
        )
        items = {row["uid"]: row for row in rows}
        if len(items) != 2:
            raise ValueError("Mimisymbic source or target item is unavailable")
        source = items[source_uid]
        target = items[target_uid]
        if (
            source["character_id"] != owner_id
            or target["character_id"] != owner_id
            or source["quantity"] < 1
            or target["quantity"] < 1
        ):
            raise ValueError("Mimisymbic items must belong to the active character")
        _validate_source_rule(db, source)
        # The source-generated target descriptor attests native root type109
        # and the eSP accessory-only predicate. Storage ownership is checked by
        # the two account-owned inventory rows above.
        appearance = db.execute(
            "SELECT appearance_ref FROM inventory_item_appearances WHERE uid=%s FOR UPDATE",
            (target_uid,),
        ).fetchone()
        definition = _target_definition(
            db, appearance["appearance_ref"] if appearance else target["reference"]
        )
        record = load(db, account_id)
        if record is None:
            raise ValueError("Missing account cosmetic schema")
        owned = tuple(
            (category, definition["appearance_ref"], 0, 0)
            for category in definition["categories"]
        )
        if any(item[:2] in {row[:2] for row in record.items} for item in owned):
            raise ValueError("Mimisymbic appearance is already learned")
        character = store.character(account_id, owner_id, db)
        if _is_equipped(character, source_uid):
            raise ValueError("Unequip the mimisymbic learning item before use")
        if _has_specific_data(db, source_uid):
            raise ValueError("Mimisymbic source has unsupported specific data")

        record = OwnedCosmetics(
            record.account_id,
            record.items + owned,
            record.selections,
            record.inactive_characters,
            record.costumes,
            record.single_selections,
        )
        db.execute(
            "INSERT INTO account_cosmetics(account_id,record) VALUES(%s,%s) "
            "ON CONFLICT(account_id) DO UPDATE SET record=EXCLUDED.record,"
            "revision=account_cosmetics.revision+1",
            (account_id, Jsonb(record.to_record())),
        )
        if source["quantity"] == 1:
            db.execute("DELETE FROM inventory_items WHERE uid=%s", (source_uid,))
        else:
            db.execute(
                "UPDATE inventory_items SET quantity=quantity-1 WHERE uid=%s",
                (source_uid,),
            )
        db.execute(
            "INSERT INTO mimisymbic_learning_receipts "
            "(account_id,source_uid,character_id,source_ref,action_id,target_uid,"
            "target_ref,categories,appearance_ref) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                account_id,
                source_uid,
                owner_id,
                SOURCE_REF,
                ACTION_ID,
                target_uid,
                target["reference"],
                list(definition["categories"]),
                definition["appearance_ref"],
            ),
        )
        return _result(
            store,
            db,
            account_id,
            owner_id,
            record,
            applied=True,
            source_uid=source_uid,
        )
