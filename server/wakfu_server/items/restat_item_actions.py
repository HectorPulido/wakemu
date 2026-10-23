"""Native Farmergency scroll resets all owned characteristics pages atomically."""
import struct

from .inventory_owner import lock_item_owner
from .simple_item_actions import _equipped, _idle

ITEM_REFERENCE = 20691
ACTION_ID = 8399


def action_class(body):
    if not isinstance(body, bytes) or len(body) < 12:
        raise ValueError("Invalid native restat item header")
    action, uid = struct.unpack_from(">iq", body)
    if action != ACTION_ID:
        return None
    if len(body) != 12 or uid <= 0:
        raise ValueError("Invalid native restat item grammar")
    return "bHx"


def cleared_sheet(blob):
    """Remove allocations only; preserve the exact native level semantics."""
    from wakfu_server.wire import proto_fields, proto_field

    if not blob:
        return blob
    fields = list(proto_fields(blob))
    if sum(tag == 24 for tag, _ in fields) != 1 or any(
        tag not in (24, 34) for tag, _ in fields
    ):
        raise ValueError("Unsupported owned characteristics page")
    return b"".join(proto_field(tag, value) for tag, value in fields if tag != 34)


def use(store, account_id, generation, character_id, body, *, in_fight):
    """Reset every durable owner's aptitude page, returning minimal UI state.

    Native confirmation text and item description explicitly say ALL pages.
    This operation does not replace gear/decks, real or modulated levels, build
    names, selection or identity. World owns the following stat publication.
    """
    if type(in_fight) is not bool or in_fight:
        raise ValueError("Reset characteristics outside combat")
    if action_class(body) != "bHx":
        raise ValueError("Unsupported native characteristics reset")
    _, uid = struct.unpack(">iq", body)
    with store.connection() as db:
        db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account_id,))
        owner_id = lock_item_owner(
            store, db, account_id, generation, character_id, (uid,)
        )
        _idle(db, owner_id, store.now())
        item = db.execute(
            "SELECT * FROM inventory_items WHERE uid=%s AND character_id=%s FOR UPDATE",
            (uid, owner_id),
        ).fetchone()
        if item is None or item["reference"] != ITEM_REFERENCE or item["quantity"] < 1:
            raise ValueError("The source does not match this native reset")
        from .haven_bag_furniture_knowledge import _rules

        rule = _rules().get(ITEM_REFERENCE, {})
        if (
            rule.get("use_action_class") != "bHx"
            or rule.get("use_action_id") != ACTION_ID
        ):
            raise ValueError("The reset differs from the active native catalog")
        character = store.character(account_id, owner_id, db)
        if _equipped(character, uid):
            raise ValueError("Unequip the scroll before using it")
        rows = list(
            db.execute(
                "SELECT build_index,aptitudes FROM character_builds WHERE character_id=%s ORDER BY build_index FOR UPDATE",
                (owner_id,),
            )
        )
        changed = []
        for row in rows:
            before = bytes(row["aptitudes"])
            after = cleared_sheet(before)
            if before != after:
                db.execute(
                    "UPDATE character_builds SET aptitudes=%s WHERE character_id=%s AND build_index=%s",
                    (after, owner_id, row["build_index"]),
                )
                changed.append(row["build_index"])
        if item["quantity"] == 1:
            db.execute(
                "DELETE FROM inventory_items WHERE uid=%s AND character_id=%s",
                (uid, owner_id),
            )
        else:
            db.execute(
                "UPDATE inventory_items SET quantity=quantity-1 WHERE uid=%s AND character_id=%s",
                (uid, owner_id),
            )
        from .consumable_characteristics import reconcile_health
        from .builds import aptitude_registry

        character = reconcile_health(db, store.character(account_id, owner_id, db))
        registry = aptitude_registry(character)
        return dict(
            character=character,
            native_class="bHx",
            consumed=1,
            applied=True,
            source_uid=uid,
            source_reference=ITEM_REFERENCE,
            reset_build_indices=changed,
            packets=[
                (12470, struct.pack(">qh", uid, -1)),
                (12103, struct.pack(">qI", owner_id, len(registry)) + registry),
            ],
            characteristics_changed=True,
        )
