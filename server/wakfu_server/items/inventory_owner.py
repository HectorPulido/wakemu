"""Resolve UID-only inventory actions to their authorized loaded character."""


class InventoryItemOwnershipError(ValueError):
    """Requested units are absent or outside the loaded owned roster."""


def lock_inventory_character(store, db, account_id, generation, character_id):
    """Use the selected main's fenced session for an active owned hero."""
    from wakfu_server.characters.heroes import session_authorized

    if type(character_id) is not int or character_id <= 0:
        raise ValueError("Invalid inventory owner")
    lease = db.execute(
        "SELECT character_id FROM sessions WHERE account_id=%s AND generation=%s "
        "AND expires_at>%s FOR UPDATE",
        (account_id, generation, store.now()),
    ).fetchone()
    if lease is None or not session_authorized(
        db,
        {
            "account_id": account_id,
            "id": character_id,
            "selected_character_id": lease["character_id"],
        },
    ):
        raise ValueError("Invalid inventory session or inactive hero")
    if (
        db.execute(
            "SELECT id FROM characters WHERE id=%s AND account_id=%s "
            "AND deleted_at IS NULL FOR UPDATE",
            (character_id, account_id),
        ).fetchone()
        is None
    ):
        raise ValueError("Invalid inventory owner")
    return character_id


def lock_item_owner(store, db, account_id, generation, character_id, uids):
    """All selected UIDs must belong to one main or active same-account hero."""
    lock_inventory_character(store, db, account_id, generation, character_id)
    identities = tuple(uids)
    if (
        not identities
        or any(type(uid) is not int or uid <= 0 for uid in identities)
        or len(set(identities)) != len(identities)
    ):
        raise ValueError("Invalid inventory item selection")
    rows = list(
        db.execute(
            "SELECT uid,character_id FROM inventory_items WHERE uid=ANY(%s)",
            (list(identities),),
        )
    )
    if len(rows) != len(set(identities)):
        raise InventoryItemOwnershipError("Inventory item is unavailable or foreign")
    owners = {row["character_id"] for row in rows}
    if len(owners) != 1:
        raise ValueError("Inventory selection spans multiple characters")
    try:
        return lock_inventory_character(store, db, account_id, generation, owners.pop())
    except ValueError as error:
        raise InventoryItemOwnershipError(
            "Inventory item is unavailable or foreign: inactive hero or owner"
        ) from error
