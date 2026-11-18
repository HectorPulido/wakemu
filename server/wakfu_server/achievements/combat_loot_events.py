"""Mission acquisition from actual delivered drops, never kill approximations.

Normal terminal progression runs after the durable loot sink in both individual
and shared combat_lifecycle paths. Overflow contributes only when subsequently
moved from temporary storage into the owner's real inventory.
"""


def indexed_references(db):
    return [
        row["reference"]
        for row in db.execute(
            "SELECT DISTINCT i.reference FROM mission_toolkit_event_index i "
            "JOIN mission_toolkit_active a USING(profile_id,version) "
            "WHERE i.kind='combat_loot' AND i.reference IS NOT NULL ORDER BY i.reference"
        ).fetchall()
    ]


def settle_received(db, store, character, *, fight_id):
    """Called inside authenticated winning progression AFTER item delivery."""
    from . import mission_toolkit

    if type(fight_id) is not int or fight_id <= 0:
        raise ValueError("Invalid delivered combat loot fight")
    references = indexed_references(db)
    if not references:
        return []
    rows = db.execute(
        "SELECT item_reference AS reference,sum(inventory_quantity)::bigint AS quantity "
        "FROM fight_drop_delivery_receipts WHERE fight_id=%s AND character_id=%s "
        "AND item_reference=ANY(%s) AND inventory_quantity>0 GROUP BY item_reference "
        "ORDER BY item_reference",
        (fight_id, character["id"], references),
    ).fetchall()
    packets = []
    for row in rows:
        if type(row["quantity"]) is not int or row["quantity"] <= 0:
            raise ValueError("Invalid actual delivered loot quantity")
        packets.extend(
            mission_toolkit.settle(
                db,
                store,
                character,
                f"combat-delivery:{fight_id}:{row['reference']}",
                "combat_loot",
                row["reference"],
                row["quantity"],
            )
        )
    return packets


def settle_temporary_claim(db, store, character, *, token, reference, quantity):
    """Only a successful locked temporary→inventory writer calls this hook."""
    from . import mission_toolkit

    if (
        not isinstance(token, str)
        or not token
        or type(reference) is not int
        or reference <= 0
        or type(quantity) is not int
        or quantity <= 0
    ):
        raise ValueError("Invalid received temporary combat loot")
    if reference not in indexed_references(db):
        return []
    return mission_toolkit.settle(
        db,
        store,
        character,
        "combat-temporary:" + token,
        "combat_loot",
        reference,
        quantity,
    )
