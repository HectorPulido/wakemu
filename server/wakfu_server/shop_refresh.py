"""Deliver committed HTTP shop purchases to the connected game session."""

import struct

from wakfu_server.inventory_items import equipment_inventory, insertion
from wakfu_server.inventory_move import synchronization


def pending(store, account_id, character, generation=None):
    """Read pending orders, then load their committed inventory and wallet."""
    from wakfu_server import shop_feedback

    with store.connection() as db:
        feedback = shop_feedback.pending(db, account_id, character, generation)
        orders = db.execute(
            "SELECT id, item_uid FROM shop_orders "
            "WHERE account_id=%s AND character_id=%s AND notified_at IS NULL "
            "ORDER BY created_at, id LIMIT 100",
            (account_id, character["id"]),
        ).fetchall()
        if not orders:
            if feedback is None:
                return None
            revision, packet = feedback
            return dict(
                character=character,
                packets=[packet],
                order_ids=[],
                feedback_revision=revision,
            )
        saved = store.character(account_id, character["id"], db)
        balance = db.execute(
            "SELECT kamas FROM account_wallets WHERE account_id=%s",
            (account_id,),
        ).fetchone()["kamas"]
    refreshed = dict(
        character,
        inventory_containers=saved["inventory_containers"],
        inventory_items=saved["inventory_items"],
        quest_items=saved.get("quest_items", []),
        kamas=balance,
    )
    purchased = {order["item_uid"] for order in orders}
    packets = [
        insertion(item, notification=True)
        for item in refreshed["inventory_items"]
        if item["uid"] in purchased
    ]
    from wakfu_server.items.quest_inventory import changes as quest_changes

    packets.extend(quest_changes(character, refreshed))
    packets.extend(
        [
            synchronization(refreshed),
            equipment_inventory(refreshed),
            (12753, struct.pack(">q", balance)),
        ]
    )
    if feedback is not None:
        packets.append(feedback[1])
    return dict(
        character=refreshed,
        packets=packets,
        order_ids=[order["id"] for order in orders],
        feedback_revision=feedback[0] if feedback is not None else None,
    )


def acknowledge(
    store, account_id, character_id, order_ids, generation=None, feedback_revision=None
):
    """Acknowledge only the orders whose packets were sent successfully."""
    if not order_ids and feedback_revision is None:
        return
    from wakfu_server import shop_feedback

    with store.connection() as db:
        shop_feedback.acknowledge(
            db, account_id, character_id, generation, feedback_revision
        )
        db.execute(
            "UPDATE shop_orders SET notified_at=now() "
            "WHERE account_id=%s AND character_id=%s AND id=ANY(%s) "
            "AND notified_at IS NULL",
            (account_id, character_id, order_ids),
        )
