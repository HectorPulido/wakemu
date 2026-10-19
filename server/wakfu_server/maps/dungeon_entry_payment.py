"""Consume native entrance items in the caller's authorized transition transaction."""


class InsufficientEntranceItems(ValueError):
    """At least one participant cannot pay with carried unprotected items."""


def _plan(db, member_ids, reference, quantity, *, lock):
    """Charge each frozen member; callers own authorization and transaction rollback.

    Ordinary items must be carried in owned bags. Equipment in any saved build
    and items offered in an active exchange cannot pay an entrance fee. Quest
    items use their native personal or account storage. Plan the whole roster
    before writing so an insufficient companion changes nothing.
    """
    from wakfu_server.craft_planner import _equipped_uids
    from wakfu_server.recycling import _offered_uids
    from wakfu_server import quest_inventory

    members = tuple(member_ids)
    if (
        not members
        or any(type(member) is not int or member <= 0 for member in members)
        or len(set(members)) != len(members)
        or type(reference) is not int
        or reference <= 0
        or type(quantity) is not int
        or not 1 <= quantity <= 32767
    ):
        raise ValueError("Invalid native entrance item payment")

    planned = []
    if reference in quest_inventory._SOURCE["account_quest_property_references"]:
        from wakfu_server.items import account_quest_inventory

        owners = list(
            db.execute(
                "SELECT id,account_id FROM characters WHERE id=ANY(%s) AND deleted_at IS NULL ORDER BY id",
                (list(members),),
            )
        )
        if len(owners) != len(members):
            raise ValueError("Native entrance member is unavailable")
        by_account = {}
        for owner in owners:
            by_account.setdefault(owner["account_id"], []).append(owner["id"])
        for account_id, owned_members in sorted(by_account.items()):
            cost = quantity * len(owned_members)
            if cost > 32767:
                raise InsufficientEntranceItems(
                    "Insufficient native account quest entrance item"
                )
            row = account_quest_inventory.payment(
                db, account_id, reference, cost, lock=lock
            )
            if row is None:
                raise InsufficientEntranceItems(
                    f"Every party member needs {quantity} of entrance item {reference}"
                )
            planned.append(
                dict(
                    row,
                    uid=None,
                    account_quest_item=True,
                    character_id=owned_members[0],
                    character_ids=tuple(owned_members),
                    consumed=cost,
                )
            )
        return tuple(planned)
    for member in sorted(members):
        if reference in quest_inventory.REFERENCES:
            row = db.execute(
                "SELECT quantity FROM character_quest_items "
                "WHERE character_id=%s AND reference=%s"
                + (" FOR UPDATE" if lock else ""),
                (member, reference),
            ).fetchone()
            if row is None or row["quantity"] < quantity:
                raise InsufficientEntranceItems(
                    f"Every party member needs {quantity} of entrance item {reference}"
                )
            planned.append(
                dict(
                    uid=None,
                    character_id=member,
                    reference=reference,
                    quantity=row["quantity"],
                    consumed=quantity,
                    quest_item=True,
                )
            )
            continue
        # Match ordinary crafting/exchange inventory eligibility. The caller
        # already holds each character aggregate lock before these item locks.
        builds = [
            {"equipment": bytes(row["equipment"]).hex()}
            for row in db.execute(
                "SELECT equipment FROM character_builds WHERE character_id=%s",
                (member,),
            )
        ]
        protected = _equipped_uids(builds) | _offered_uids(db, member)
        rows = db.execute(
            "SELECT i.uid,i.character_id,i.quantity FROM inventory_items i "
            "JOIN inventory_containers c ON c.uid=i.container "
            "AND c.character_id=i.character_id "
            "WHERE i.character_id=%s AND i.reference=%s AND c.kind IN (0,1,2,3) "
            "ORDER BY i.uid" + (" FOR UPDATE OF i" if lock else ""),
            (member, reference),
        )
        remaining = quantity
        for row in rows:
            if row["uid"] in protected:
                continue
            taken = min(remaining, row["quantity"])
            planned.append(dict(row, consumed=taken, reference=reference))
            remaining -= taken
            if not remaining:
                break
        if remaining:
            raise InsufficientEntranceItems(
                f"Every party member needs {quantity} of entrance item {reference}"
            )

    return tuple(planned)


def available(db, character_id, reference, quantity):
    """Read-only UI eligibility; consume revalidates while holding item locks."""
    try:
        _plan(db, (character_id,), reference, quantity, lock=False)
    except InsufficientEntranceItems:
        return False
    return True


def consume(db, member_ids, reference, quantity):
    """Debit a pre-authorized roster inside the caller's transition transaction."""
    planned = _plan(db, member_ids, reference, quantity, lock=True)
    for row in planned:
        if row.get("account_quest_item"):
            from wakfu_server.items import account_quest_inventory

            account_quest_inventory.consume(
                db, row["account_id"], row["reference"], row["consumed"]
            )
        elif row.get("quest_item"):
            if row["consumed"] == row["quantity"]:
                db.execute(
                    "DELETE FROM character_quest_items WHERE character_id=%s AND reference=%s",
                    (row["character_id"], row["reference"]),
                )
            else:
                db.execute(
                    "UPDATE character_quest_items SET quantity=quantity-%s "
                    "WHERE character_id=%s AND reference=%s",
                    (row["consumed"], row["character_id"], row["reference"]),
                )
        elif row["consumed"] == row["quantity"]:
            db.execute("DELETE FROM inventory_items WHERE uid=%s", (row["uid"],))
        else:
            db.execute(
                "UPDATE inventory_items SET quantity=quantity-%s WHERE uid=%s",
                (row["consumed"], row["uid"]),
            )
    return tuple(planned)
