"""Authorize native background-book reads without consuming reusable books.

Original bHU opens cYN before submitting cqd13220. The server therefore
validates custody and the immutable background action; it must not reopen that
UI or invent an animation from the unused second native action parameter.
"""
from functools import lru_cache
import struct

from .inventory_owner import lock_item_owner
from .simple_item_actions import _criterion, _equipped, _idle

SOURCE_SHA256 = "f83a6050701432d4978c565615a7f1880ea221a3b6b975ca055a6005ef51426c"


@lru_cache(maxsize=1)
def _action_classes():
    from .haven_bag_furniture_knowledge import _rules

    result = {}
    for row in _rules().values():
        identity = row.get("use_action_id")
        if identity is not None:
            result.setdefault(identity, set()).add(row.get("use_action_class"))
    return result


def action_class(body):
    """Identify bHU while retaining its exact twelve-byte native grammar."""
    if not isinstance(body, bytes) or len(body) < 12:
        raise ValueError("Invalid native book action request")
    action_id, uid = struct.unpack_from(">iq", body)
    if action_id <= 0 or uid <= 0:
        raise ValueError("Invalid native book action identity")
    classes = _action_classes().get(action_id, set())
    if "bHU" not in classes:
        return None
    if classes != {"bHU"} or len(body) != 12:
        raise ValueError("Invalid native book action grammar")
    return "bHU"


def use(
    store, account_id, generation, character_id, body, *, in_fight, native_map_id=None
):
    """Validate one owned read; repeated reads preserve the same physical UID."""
    if type(in_fight) is not bool or in_fight:
        raise ValueError("Read this book outside combat")
    if action_class(body) != "bHU":
        raise ValueError("Unsupported native book action")
    action_id, source_uid = struct.unpack(">iq", body)
    with store.connection() as db:
        db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account_id,))
        owner_id = lock_item_owner(
            store, db, account_id, generation, character_id, (source_uid,)
        )
        _idle(db, owner_id, store.now())
        item = db.execute(
            "SELECT * FROM inventory_items WHERE uid=%s AND character_id=%s FOR UPDATE",
            (source_uid, owner_id),
        ).fetchone()
        if item is None or item["quantity"] < 1:
            raise ValueError("The book is unavailable or belongs to another character")
        rule = db.execute(
            "SELECT * FROM native_book_item_actions WHERE item_ref=%s",
            (item["reference"],),
        ).fetchone()
        if (
            rule is None
            or rule["action_id"] != action_id
            or rule["source_sha256"] != SOURCE_SHA256
            or type(rule["background_id"]) is not int
            or rule["background_id"] <= 0
            or rule["consumes_source"] is not False
        ):
            raise ValueError("The book does not match its qualified native action")
        from .haven_bag_furniture_knowledge import _rules

        published = _rules().get(item["reference"], {})
        if (
            published.get("use_action_class") != "bHU"
            or published.get("use_action_id") != action_id
        ):
            raise ValueError("The book action differs from the active native catalog")
        character = store.character(account_id, owner_id, db)
        if _equipped(character, source_uid):
            raise ValueError("Unequip the book before reading it")
        if not _criterion(
            store, db, account_id, character, rule["criterion"], native_map_id
        ):
            raise ValueError("The native book conditions are not satisfied")
        # All 160 installed bHU actions have native aLQ.cqa/foH.gie=false.
        # Their local UI is already open. No inventory delta or fabricated
        # effect/ack packet is necessary for this nonmutating read.
        return dict(
            character=character,
            packets=[],
            applied=False,
            validated=True,
            native_class="bHU",
            consumed=0,
            background_id=rule["background_id"],
            source_uid=source_uid,
            source_reference=item["reference"],
            native_parameters=rule["native_parameters"],
        )
