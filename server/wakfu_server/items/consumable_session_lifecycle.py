"""Transaction-bound online clocks at observed character/session departures."""


def pause_current_company(store, db, account_id, generation):
    """Pause only the still-owned selected company before its lease changes.

    For takeover, generation must come from the actual live World connection.
    Missing/expired/replaced leases never justify charging an unobserved gap.
    The caller must commit the departure/CAS in this same transaction.
    """
    from psycopg.pq import TransactionStatus
    from wakfu_server.consumable_world_lifecycle import company_membership

    if db.info.transaction_status != TransactionStatus.INTRANS:
        raise ValueError("Consumable departure requires the session transaction")
    if (
        type(account_id) is not int
        or account_id <= 0
        or not isinstance(generation, str)
        or not generation
        or len(generation) > 128
    ):
        raise ValueError("Invalid consumable departure lease")
    db.execute("SELECT id FROM accounts WHERE id=%s FOR NO KEY UPDATE", (account_id,))
    session = db.execute(
        "SELECT character_id FROM sessions WHERE account_id=%s AND generation=%s "
        "AND expires_at>%s FOR UPDATE",
        (account_id, generation, store.now()),
    ).fetchone()
    if session is None or session["character_id"] is None:
        return ()
    main_id = session["character_id"]
    roster = db.execute(
        "SELECT leader_id FROM account_hero_rosters WHERE account_id=%s FOR UPDATE",
        (account_id,),
    ).fetchone()
    identities = {main_id}
    if roster is not None and roster["leader_id"] == main_id:
        identities.update(
            row["character_id"]
            for row in db.execute(
                "SELECT character_id FROM account_hero_slots WHERE account_id=%s "
                "ORDER BY slot FOR UPDATE",
                (account_id,),
            ).fetchall()
        )
    company_membership(store, db, account_id, generation, identities, ())
    return tuple(sorted(identities))
