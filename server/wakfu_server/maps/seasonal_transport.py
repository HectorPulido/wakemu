"""Public event transport criteria with reviewed year-round date windows."""

from . import seasonal_access, transport_criteria


def evaluate(
    expression, character, destination_map_id, *, now_ms, achievement_complete=None
):
    expression = seasonal_access.open_event_calendar(
        expression, destination_map_id=destination_map_id
    )
    return transport_criteria.evaluate(
        expression,
        character,
        now_ms=now_ms,
        achievement_complete=achievement_complete,
    )


def evaluator(store, character):
    """Preserve seasonal calendar policy and the requesting owner's ledger."""
    owned = transport_criteria.evaluator(store, character)

    def allowed(expression, actor, destination_map_id):
        expression = seasonal_access.open_event_calendar(
            expression, destination_map_id=destination_map_id
        )
        return owned(expression, actor)

    return allowed


def transition(store, account_id, generation, character, route):
    """Debit native public-entry items in the same fenced map transaction."""
    from .dungeon_entry_payment import consume

    price = route["item_payment"]
    with store.connection() as db:
        db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account_id,))
        store.lock_character(db, account_id, generation, character["id"], selected=True)
        current = store.character(account_id, character["id"], db)
        authority = None

        def achievement_complete(identity):
            nonlocal authority
            if authority is None:
                from .dungeon_achievement_authority import queries_from_snapshot

                row = db.execute(
                    "SELECT snapshot FROM character_achievement_authority "
                    "WHERE character_id=%s FOR SHARE",
                    (current["id"],),
                ).fetchone()
                authority = queries_from_snapshot(
                    None if row is None else row["snapshot"]
                )
            return authority["IsAchievementComplete"](identity)

        if (
            evaluate(
                route["criterion"],
                current,
                route["destination"]["map_id"],
                now_ms=int(store.clock() * 1000),
                achievement_complete=achievement_complete,
            )
            is not True
        ):
            raise ValueError("Native teleporter access criterion is not met")
        consume(db, (character["id"],), price["reference"], price["quantity"])
        return store.transition_map_in_transaction(
            db, account_id, generation, character["id"], character, route["destination"]
        )
