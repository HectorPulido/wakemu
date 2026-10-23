"""Native 13284 Mimobionte fusion with preserved statistical item identity.

Original dcW/bKL sends Mimobionte UID, statistical UID, then appearance UID.
Original UI explicitly consumes the Mimobionte and appearance donor, retaining
only the statistical item with fnR.VW(bkK.f(donor)) as its visual override.
"""
import struct

from .inventory_owner import lock_inventory_character, lock_item_owner
from .simple_item_actions import _equipped, _idle

SOURCE_REF = 19292
SOURCE_ACTION_ID = 7325
TARGETS_SHA256 = "125dc67c3b12eeb6f912c593fa36d2e1053dad78d80be8e60678f79573cfe993"


def decode(body):
    if not isinstance(body, bytes) or len(body) != 24:
        raise ValueError("Native item fusion requires exactly three item UIDs")
    values = struct.unpack(">qqq", body)
    if any(value <= 0 for value in values) or len(set(values)) != 3:
        raise ValueError("Native fusion needs three distinct positive item UIDs")
    return values


def _target(db, reference):
    row = db.execute(
        "SELECT * FROM native_item_fusion_targets WHERE reference=%s", (reference,)
    ).fetchone()
    if row is None or row["source_sha256"] != TARGETS_SHA256:
        raise ValueError("This native equipment cannot receive or donate an appearance")
    return row


def _result(store, db, account_id, character_id, *, applied, stat_uid, appearance_ref):
    from .inventory_items import equipment_inventory
    from .inventory_move import synchronization

    character = store.character(account_id, character_id, db)
    return dict(
        character=character,
        packets=[synchronization(character), equipment_inventory(character)],
        applied=applied,
        native_class="bHT",
        stat_uid=stat_uid,
        appearance_ref=appearance_ref,
        consumed=2 if applied else 0,
    )


def use(store, account_id, generation, character_id, body, *, in_fight):
    """Commit both native source debits and the target appearance atomically."""
    mimibionte_uid, stat_uid, skin_uid = decode(body)
    if type(in_fight) is not bool or in_fight:
        raise ValueError("Item appearance fusion is unavailable during combat")
    with store.connection() as db:
        db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account_id,))
        lock_inventory_character(store, db, account_id, generation, character_id)
        prior = db.execute(
            "SELECT * FROM item_fusion_receipts WHERE account_id=%s "
            "AND mimibionte_uid=%s AND stat_uid=%s AND skin_uid=%s",
            (account_id, mimibionte_uid, stat_uid, skin_uid),
        ).fetchone()
        if prior is not None:
            owner_id = lock_inventory_character(
                store, db, account_id, generation, prior["character_id"]
            )
            _idle(db, owner_id, store.now())
            return _result(
                store,
                db,
                account_id,
                owner_id,
                applied=False,
                stat_uid=stat_uid,
                appearance_ref=prior["appearance_ref"],
            )
        owner_id = lock_item_owner(
            store,
            db,
            account_id,
            generation,
            character_id,
            (mimibionte_uid, stat_uid, skin_uid),
        )
        _idle(db, owner_id, store.now())
        rows = list(
            db.execute(
                "SELECT * FROM inventory_items WHERE uid=ANY(%s) ORDER BY uid FOR UPDATE",
                ([mimibionte_uid, stat_uid, skin_uid],),
            )
        )
        items = {row["uid"]: row for row in rows}
        if len(items) != 3 or any(row["character_id"] != owner_id for row in rows):
            raise ValueError(
                "Fusion items must belong to the same active owned character"
            )
        source, stat, skin = (
            items[uid] for uid in (mimibionte_uid, stat_uid, skin_uid)
        )
        from .haven_bag_furniture_knowledge import _rules

        source_rule = _rules().get(source["reference"], {})
        if (
            source["reference"] != SOURCE_REF
            or source["quantity"] < 1
            or source_rule.get("use_action_class") != "bHT"
            or source_rule.get("use_action_id") != SOURCE_ACTION_ID
        ):
            raise ValueError("The source is not the native Mimobionte")
        if stat["quantity"] != 1 or skin["quantity"] != 1:
            raise ValueError("Separate equipment stacks before fusing their appearance")
        character = store.character(account_id, owner_id, db)
        if any(_equipped(character, uid) for uid in items):
            raise ValueError("Unequip fusion items from every build first")
        stat_definition, skin_definition = (
            _target(db, row["reference"]) for row in (stat, skin)
        )
        if stat_definition["normalized_type"] != skin_definition["normalized_type"]:
            raise ValueError("Native fusion requires equipment of the same type")
        # Original native UI text specifies this server eligibility condition;
        # current frf.d client validation does not itself check the level.
        if skin_definition["item_level"] > stat_definition["item_level"]:
            raise ValueError(
                "The appearance donor cannot exceed the statistical item level"
            )
        appearances = {
            row["uid"]: row["appearance_ref"]
            for row in db.execute(
                "SELECT uid,appearance_ref FROM inventory_item_appearances "
                "WHERE uid=ANY(%s) FOR UPDATE",
                ([stat_uid, skin_uid],),
            )
        }
        appearance_ref = appearances.get(skin_uid, skin["reference"])
        current_appearance = appearances.get(stat_uid, stat["reference"])
        if appearance_ref in (current_appearance, stat["reference"]):
            raise ValueError("The items already have the same native appearance")
        _target(db, appearance_ref)
        db.execute(
            "INSERT INTO inventory_item_appearances(uid,appearance_ref) VALUES(%s,%s) "
            "ON CONFLICT(uid) DO UPDATE SET appearance_ref=EXCLUDED.appearance_ref",
            (stat_uid, appearance_ref),
        )
        # The target UID, reference, unit quantity, location, elements, sockets,
        # binding, and every saved build reference remain exactly unchanged.
        db.execute("DELETE FROM inventory_items WHERE uid=%s", (skin_uid,))
        if source["quantity"] == 1:
            db.execute("DELETE FROM inventory_items WHERE uid=%s", (mimibionte_uid,))
        else:
            db.execute(
                "UPDATE inventory_items SET quantity=quantity-1 WHERE uid=%s",
                (mimibionte_uid,),
            )
        db.execute(
            "INSERT INTO item_fusion_receipts(account_id,character_id,mimibionte_uid,stat_uid,"
            "skin_uid,stat_ref,skin_ref,appearance_ref) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                account_id,
                owner_id,
                mimibionte_uid,
                stat_uid,
                skin_uid,
                stat["reference"],
                skin["reference"],
                appearance_ref,
            ),
        )
        return _result(
            store,
            db,
            account_id,
            owner_id,
            applied=True,
            stat_uid=stat_uid,
            appearance_ref=appearance_ref,
        )
