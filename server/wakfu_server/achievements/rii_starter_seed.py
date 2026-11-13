"""One-time reconstructed seed supply for Rii's ecosystem lesson.

This is a local recovery policy, not a recovered original NPC reward. The
caller starts quest 5155 in the same owned-character transaction; planting and
harvesting still use their ordinary native mechanics.
"""

from . import rewards, storage


def grant_if_missing(db, store, character):
    """Bring the student's supply up to three seeds on initial acceptance."""
    from wakfu_server.planting import SEEDS

    seed = SEEDS.get(31007)
    if not seed or seed.get("resource_reference") != 825:
        raise ValueError("Celestial flower seed differs from native catalog")
    rows = db.execute(
        "SELECT quantity FROM inventory_items WHERE character_id=%s AND reference=%s "
        "AND quantity>0 FOR UPDATE",
        (character["id"], 31007),
    ).fetchall()
    quantity = max(0, 3 - sum(row["quantity"] for row in rows))
    if not quantity:
        return []
    if not storage.record_event(
        db,
        character["id"],
        "rii-starter-flower-seed:5155",
        {
            "kind": "reconstructed_rii_starter_seed",
            "quest_id": 5155,
            "reference": 31007,
            "quantity": quantity,
        },
    ):
        return []
    return rewards._item(db, store, character, 31007, quantity)


def refresh_after_delivery(store, account_id, character, packets):
    """Refresh only the current owned character after inventory publication."""
    if not any(opcode in (12470, 12471) for opcode, _ in packets):
        return character
    from wakfu_server.inventory_move import reload_inventory

    return reload_inventory(store, account_id, character)
