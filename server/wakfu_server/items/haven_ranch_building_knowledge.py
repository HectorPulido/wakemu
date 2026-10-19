"""Native bIA Ranch building learning, separate from bIx decoration ownership."""
import struct

from .inventory_owner import lock_inventory_character, lock_item_owner


def library_payload(references):
    """Original fxS.foH/a: empty owned animals/biomes plus fBX known/new sets.

    Ranch animals and breeding have no server-owned implementation here. Never
    import another account's captured component to fill those empty sections.
    """
    refs = sorted(references)
    if len(refs) != len(set(refs)) or any(
        type(ref) is not int or not 0 < ref < 2**31 for ref in refs
    ):
        raise ValueError("Invalid native Ranch building references")
    values = struct.pack(">I", len(refs)) + b"".join(
        struct.pack(">i", ref) for ref in refs
    )
    library = values + values  # fBX.abO adds newly learned entries to both sets.
    animals = struct.pack(">II", 0, 0)
    biomes = b"\x00\x00"  # Original empty fBI.aqv, verified by native roundtrip.
    return b"".join(
        struct.pack(">I", len(part)) + part for part in (animals, biomes, library)
    )


def _snapshot(db, account_id):
    refs = [
        row["building_ref"]
        for row in db.execute(
            "SELECT building_ref FROM account_ranch_building_knowledge "
            "WHERE account_id=%s ORDER BY building_ref",
            (account_id,),
        )
    ]
    return 13873, struct.pack(">II", 1, 18) + library_payload(refs)


def packet(store, account_id):
    with store.connection() as db:
        return _snapshot(db, account_id)


def learn(store, account_id, generation, character_id, body):
    if not isinstance(body, bytes) or len(body) != 12:
        raise ValueError("Ranch building learning requires exactly 12 request bytes")
    action_id, source_uid = struct.unpack(">iq", body)
    if action_id <= 0 or source_uid <= 0:
        raise ValueError("Invalid Ranch building learning action or item UID")
    with store.connection() as db:
        db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account_id,))
        lock_inventory_character(store, db, account_id, generation, character_id)
        prior = db.execute(
            "SELECT * FROM ranch_building_learning_receipts "
            "WHERE account_id=%s AND source_uid=%s",
            (account_id, source_uid),
        ).fetchone()
        if prior is not None:
            character_id = lock_inventory_character(
                store, db, account_id, generation, prior["character_id"]
            )
            if prior["action_id"] != action_id:
                raise ValueError(
                    "Ranch building learning receipt does not match request"
                )
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
            raise ValueError("Ranch building learning item unavailable or foreign")
        native = db.execute(
            "SELECT * FROM native_ranch_building_learning_actions WHERE item_ref=%s",
            (item["reference"],),
        ).fetchone()
        from .haven_bag_furniture_knowledge import _rules

        rule = _rules().get(item["reference"])
        if (
            native is None
            or native["native_class"] != "bIA"
            or native["action_id"] != action_id
            or rule is None
            or rule.get("use_action_class") != "bIA"
            or rule.get("use_action_id") != action_id
            or rule.get("use_has_criteria") is not False
        ):
            raise ValueError(
                "Unsupported native Ranch building learning action or criteria"
            )
        from .profession_store import stored_level

        profession_level = stored_level(db, account_id, native["profession_id"])
        if (0 if profession_level is None else profession_level) < native[
            "minimum_level"
        ]:
            raise ValueError(
                "Profession level does not meet native Ranch building requirement"
            )
        from .wire import proto_fields

        character = store.character(account_id, character_id, db)
        for build in character.get("builds", {}).values():
            for tag, value in proto_fields(bytes.fromhex(build["equipment"])):
                if tag == 10 and dict(proto_fields(value)).get(8) == source_uid:
                    raise ValueError(
                        "Unequip the Ranch building learning item before use"
                    )
        for table in (
            "inventory_item_elements",
            "inventory_item_shards",
            "inventory_mounts",
        ):
            if db.execute(
                f"SELECT 1 FROM {table} WHERE uid=%s", (source_uid,)
            ).fetchone():
                raise ValueError(
                    "Ranch building learning item has unsupported specific data"
                )
        refs = native["building_refs"]
        library_payload(refs)  # Validate the exact immutable native target domain.
        known = {
            row["building_ref"]
            for row in db.execute(
                "SELECT building_ref FROM account_ranch_building_knowledge "
                "WHERE account_id=%s ORDER BY building_ref",
                (account_id,),
            )
        }
        added = sorted(set(refs) - known)
        if not added:
            raise ValueError("Ranch building is already learned")
        for ref in added:
            db.execute(
                "INSERT INTO account_ranch_building_knowledge(account_id,building_ref) "
                "VALUES(%s,%s)",
                (account_id, ref),
            )
        if item["quantity"] == 1:
            db.execute("DELETE FROM inventory_items WHERE uid=%s", (source_uid,))
        else:
            db.execute(
                "UPDATE inventory_items SET quantity=quantity-1 WHERE uid=%s",
                (source_uid,),
            )
        db.execute(
            "INSERT INTO ranch_building_learning_receipts"
            "(account_id,source_uid,character_id,source_ref,action_id,learned_refs) "
            "VALUES(%s,%s,%s,%s,%s,%s)",
            (account_id, source_uid, character_id, item["reference"], action_id, added),
        )
        return {
            "character": store.character(account_id, character_id, db),
            "packets": [
                (12470, struct.pack(">qh", source_uid, -1)),
                _snapshot(db, account_id),
            ],
            "applied": True,
        }
