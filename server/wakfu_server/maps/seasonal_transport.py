"""Public event transport criteria with reviewed year-round date windows."""

from . import seasonal_access, transport_criteria


def evaluate(expression, character, destination_map_id, *, now_ms):
    expression = seasonal_access.open_event_calendar(
        expression, destination_map_id=destination_map_id
    )
    return transport_criteria.evaluate(expression, character, now_ms=now_ms)


def transition(store, account_id, generation, character, route):
    """Debit native public-entry items in the same fenced map transaction."""
    from .dungeon_entry_payment import consume

    price = route["item_payment"]
    with store.connection() as db:
        db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account_id,))
        store.lock_character(db, account_id, generation, character["id"], selected=True)
        current = store.character(account_id, character["id"], db)
        if (
            evaluate(
                route["criterion"],
                current,
                route["destination"]["map_id"],
                now_ms=int(store.clock() * 1000),
            )
            is not True
        ):
            raise ValueError("Native teleporter access criterion is not met")
        consume(db, (character["id"],), price["reference"], price["quantity"])
        return store.transition_map_in_transaction(
            db, account_id, generation, character["id"], character, route["destination"]
        )
