"""Native bIB/bIz recipe books backed by account craft knowledge."""

import struct

from wakfu_server.inventory_owner import lock_inventory_character, lock_item_owner
from wakfu_server.wire import proto_fields
from wakfu_server.profession_store import account_packet


def _validated_rule(rule, action_id):
    if (
        rule is None
        or rule["action_id"] != action_id
        or rule["native_class"] not in ("bIB", "bIz")
        or rule["has_criteria"] is not False
        or type(rule["profession_id"]) is not int
        or rule["profession_id"] <= 0
    ):
        raise ValueError("Unsupported native recipe learning action")
    recipes = rule["recipe_ids"]
    if (
        not isinstance(recipes, (list, tuple))
        or not recipes
        or len(recipes) > 65536
        or any(
            type(identity) is not int or not 0 < identity < 2**31
            for identity in recipes
        )
        or len(set(recipes)) != len(recipes)
        or (rule["native_class"] == "bIB" and len(recipes) != 1)
    ):
        raise ValueError("Invalid native recipe learning parameters")
    from wakfu_server.haven_bag_furniture_knowledge import _rules

    active = _rules().get(rule["item_ref"])
    if (
        active is None
        or active.get("use_action_class") != rule["native_class"]
        or active.get("use_action_id") != action_id
        or active.get("use_has_criteria") is not False
    ):
        raise ValueError("Recipe action does not match the published native catalog")
    # Native eTe.fM stores recipe IDs without resolving eTw's recipe catalog.
    # Retired book outputs remain knowledge, not authority to execute a craft.
    return set(recipes)


def learn(store, account_id, generation, character_id, body):
    """Consume one owned book only when at least one native recipe is new."""
    if not isinstance(body, bytes) or len(body) != 12:
        raise ValueError("Recipe learning requires exactly 12 request bytes")
    action_id, source_uid = struct.unpack(">iq", body)
    if action_id <= 0 or source_uid <= 0:
        raise ValueError("Invalid recipe learning action or item UID")
    with store.connection() as db:
        # Match other account collection writers: account, lease, inventory owner.
        db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account_id,))
        lock_inventory_character(store, db, account_id, generation, character_id)
        prior = db.execute(
            "SELECT * FROM recipe_learning_receipts WHERE account_id=%s AND source_uid=%s",
            (account_id, source_uid),
        ).fetchone()
        if prior is not None:
            if prior["action_id"] != action_id:
                raise ValueError("Recipe learning receipt does not match request")
            owner_id = lock_inventory_character(
                store, db, account_id, generation, prior["character_id"]
            )
            return dict(
                character=store.character(account_id, owner_id, db),
                packets=[account_packet(db, account_id)],
                applied=False,
            )
        owner_id = lock_item_owner(
            store, db, account_id, generation, character_id, (source_uid,)
        )
        item = db.execute(
            "SELECT * FROM inventory_items WHERE uid=%s AND character_id=%s FOR UPDATE",
            (source_uid, owner_id),
        ).fetchone()
        if item is None or item["quantity"] < 1:
            raise ValueError("Recipe learning item unavailable or foreign")
        rule = db.execute(
            "SELECT * FROM native_recipe_learning_actions WHERE item_ref=%s",
            (item["reference"],),
        ).fetchone()
        recipes = _validated_rule(rule, action_id)
        state = db.execute(
            "SELECT actions FROM account_professions WHERE account_id=%s AND profession_id=%s FOR UPDATE",
            (account_id, rule["profession_id"]),
        ).fetchone()
        if state is None:
            raise ValueError("Recipe learning requires its native profession")
        known = set(state["actions"])
        # bIz checks ALL requested recipes; partial knowledge still allows use.
        if recipes <= known:
            raise ValueError("Recipe is already learned")
        from wakfu_server.craft_catalog import load_catalog

        catalog = load_catalog()
        # chh requires a current native recipe to deliver cut13186's listener.
        # Absolute account state below also restores retired recipe knowledge.
        learned_packets = [
            (13186, struct.pack(">ii", rule["profession_id"], identity))
            for identity in sorted(recipes - known)
            if identity in catalog.recipes
            and catalog.recipes[identity].get("profession_id") == rule["profession_id"]
        ]
        combined = sorted(known | recipes)
        if len(combined) > 65536:
            raise ValueError("Native recipe knowledge capacity exceeded")
        character = store.character(account_id, owner_id, db)
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
                raise ValueError("Recipe learning item has unsupported specific data")
        db.execute(
            "UPDATE account_professions SET actions=%s WHERE account_id=%s AND profession_id=%s",
            (combined, account_id, rule["profession_id"]),
        )
        if item["quantity"] == 1:
            db.execute("DELETE FROM inventory_items WHERE uid=%s", (source_uid,))
        else:
            db.execute(
                "UPDATE inventory_items SET quantity=quantity-1 WHERE uid=%s",
                (source_uid,),
            )
        db.execute(
            "INSERT INTO recipe_learning_receipts(account_id,source_uid,character_id,source_ref,"
            "action_id,profession_id,recipe_ids) VALUES(%s,%s,%s,%s,%s,%s,%s)",
            (
                account_id,
                source_uid,
                owner_id,
                item["reference"],
                action_id,
                rule["profession_id"],
                sorted(recipes),
            ),
        )
        return dict(
            character=store.character(account_id, owner_id, db),
            packets=[(12470, struct.pack(">qh", source_uid, -1))]
            + learned_packets
            + [account_packet(db, account_id)],
            applied=True,
        )
