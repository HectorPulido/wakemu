"""Native bHY single-use emotes; item authority never grants learned knowledge."""
import struct
from functools import lru_cache

from wakfu_server.haven_bag_furniture_knowledge import _rules
from wakfu_server.inventory_owner import lock_item_owner


@lru_cache(maxsize=1)
def _actions():
    return frozenset(
        row["use_action_id"]
        for row in _rules().values()
        if row.get("use_action_class") == "bHY"
    )


def action_class(body):
    if not isinstance(body, bytes) or len(body) < 12:
        raise ValueError("Invalid native emote item request")
    action, uid = struct.unpack_from(">iq", body)
    if action not in _actions():
        return None
    if len(body) != 20 or uid <= 0:
        raise ValueError("Native emote item requires its target suffix")
    return "bHY"


def play(
    store,
    account_id,
    generation,
    character,
    body,
    *,
    resolve_target,
    in_fight,
    occupied=lambda _actor_id: False,
):
    """Consume one owned source atomically with validated occupation preparation."""
    if action_class(body) != "bHY":
        raise ValueError("Not a native emote item action")
    action_id, source_uid, target_id = struct.unpack(">iqq", body)
    from wakfu_server import emotes
    from wakfu_server.simple_item_actions import _idle, _equipped

    with store.connection() as db:
        character_id = lock_item_owner(
            store, db, account_id, generation, character["id"], (source_uid,)
        )
        if character_id != character["id"]:
            raise ValueError("Emote item requires its active actor context")
        _idle(db, character_id, store.now())
        if (
            character.get("hp", 0) <= 0
            or in_fight(character_id)
            or occupied(character_id)
        ):
            raise ValueError("World emotes cannot interrupt combat")
        item = db.execute(
            "SELECT i.* FROM inventory_items i JOIN inventory_containers c ON c.uid=i.container "
            "WHERE i.uid=%s AND i.character_id=%s AND c.character_id=%s FOR UPDATE OF i",
            (source_uid, character_id, character_id),
        ).fetchone()
        if item is None or item["quantity"] <= 0:
            raise ValueError("Emote item is unavailable or outside owned inventory")
        rule = db.execute(
            "SELECT * FROM native_emote_item_actions WHERE item_ref=%s",
            (item["reference"],),
        ).fetchone()
        native = _rules().get(item["reference"])
        if (
            rule is None
            or rule["action_id"] != action_id
            or rule["has_criteria"]
            or native is None
            or native.get("use_action_class") != "bHY"
            or native.get("use_action_id") != action_id
        ):
            raise ValueError("Unverified native emote item action")
        refreshed = store.character(account_id, character_id, db)
        from wakfu_server.consumable_criteria import evaluate

        if not evaluate(rule["use_criteria"], refreshed):
            raise ValueError("Native emote item USE criterion is not satisfied")
        if _equipped(refreshed, source_uid):
            raise ValueError("Unequip the emote source first")
        for table in (
            "inventory_item_elements",
            "inventory_item_shards",
            "inventory_mounts",
        ):
            if db.execute(
                f"SELECT 1 FROM {table} WHERE uid=%s", (source_uid,)
            ).fetchone():
                raise ValueError("Unsupported emote item specific data")
        # Live occupation state is not persisted in the character record.
        refreshed.update(
            {k: v for k, v in character.items() if k.startswith("_emote_")}
        )
        prepared = emotes.prepare_authorized_occupation(
            db,
            refreshed,
            rule["emote_id"],
            target_id,
            resolve_target=resolve_target,
            in_fight=in_fight,
            occupied=occupied,
        )
        if item["quantity"] == 1:
            db.execute("DELETE FROM inventory_items WHERE uid=%s", (source_uid,))
        else:
            db.execute(
                "UPDATE inventory_items SET quantity=quantity-1 WHERE uid=%s",
                (source_uid,),
            )
        return dict(
            character=store.character(account_id, character_id, db),
            applied=True,
            packets=[(12470, struct.pack(">qh", source_uid, -1))],
            **prepared,
        )
