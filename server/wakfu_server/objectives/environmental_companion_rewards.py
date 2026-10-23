"""Completion-frozen companion XP for durable environmental entitlements only.

Recipients are captured when objectives complete. Settlement consumes the
owner's actual committed XP delta, never the component's advertised amount.
The caller owns the encompassing completion/reward transaction and lease.
"""


def _identity(account_id, character_id, entitlement_id):
    if any(
        type(value) is not int or value <= 0
        for value in (account_id, character_id, entitlement_id)
    ):
        raise ValueError("Invalid environmental companion reward owner")


def freeze(db, *, entitlement_id, account_id, character_id, completed_at_ms):
    """Freeze the loaded owner company exactly once, including an empty roster."""
    _identity(account_id, character_id, entitlement_id)
    if type(completed_at_ms) is not int or completed_at_ms < 0:
        raise ValueError("Invalid environmental completion clock")
    entitlement = db.execute(
        "SELECT account_id,character_id,companions_frozen_at_ms FROM environmental_reward_entitlements "
        "WHERE entitlement_id=%s FOR UPDATE",
        (entitlement_id,),
    ).fetchone()
    if entitlement is None or (
        entitlement["account_id"],
        entitlement["character_id"],
    ) != (account_id, character_id):
        raise ValueError("Missing owned environmental entitlement")
    if entitlement["companions_frozen_at_ms"] is not None:
        return tuple(
            db.execute(
                "SELECT * FROM environmental_entitlement_companions WHERE entitlement_id=%s ORDER BY companion_id",
                (entitlement_id,),
            ).fetchall()
        )
    # Selected main and its genuinely loaded heroes share one session anchor.
    # A stored roster belonging to an inactive leader does not load companions.
    # One MVCC statement freezes the visible loaded company at completion.
    # Taking another participant's session/account locks while holding the
    # shared event would invert the ordinary owner -> event lock order.
    db.execute(
        "INSERT INTO environmental_entitlement_companions "
        "(entitlement_id,companion_id,account_id,owner_character_id,frozen_at_ms) "
        "SELECT %s,c.id,%s,%s,%s FROM account_companion_slots slots "
        "JOIN account_companions c ON c.id=slots.companion_id AND c.account_id=slots.account_id "
        "WHERE slots.account_id=%s AND slots.owner_character_id=%s AND c.linked AND c.unlocked "
        "AND EXISTS(SELECT 1 FROM sessions s WHERE s.account_id=%s "
        "AND s.expires_at>to_timestamp(%s/1000.0) "
        "AND (s.character_id=%s OR EXISTS(SELECT 1 FROM account_hero_rosters r "
        "JOIN account_hero_slots h USING(account_id) WHERE r.account_id=s.account_id "
        "AND r.leader_id=s.character_id AND h.character_id=%s))) ORDER BY c.id",
        (
            entitlement_id,
            account_id,
            character_id,
            completed_at_ms,
            account_id,
            character_id,
            account_id,
            completed_at_ms,
            character_id,
            character_id,
        ),
    )
    db.execute(
        "UPDATE environmental_reward_entitlements SET companions_frozen_at_ms=%s WHERE entitlement_id=%s",
        (completed_at_ms, entitlement_id),
    )
    return tuple(
        db.execute(
            "SELECT * FROM environmental_entitlement_companions WHERE entitlement_id=%s ORDER BY companion_id",
            (entitlement_id,),
        ).fetchall()
    )


def grant(db, store, *, entitlement_id, account_id, character_id, owner_xp):
    """Award the frozen recipients once in the owner's actual reward transaction."""
    from wakfu_server import companions

    _identity(account_id, character_id, entitlement_id)
    amount = companions.owner_experience_award(owner_xp)
    entitlement = db.execute(
        "SELECT account_id,character_id,companions_frozen_at_ms FROM environmental_reward_entitlements "
        "WHERE entitlement_id=%s FOR UPDATE",
        (entitlement_id,),
    ).fetchone()
    if (
        entitlement is None
        or (entitlement["account_id"], entitlement["character_id"])
        != (account_id, character_id)
        or entitlement["companions_frozen_at_ms"] is None
    ):
        raise ValueError("Missing frozen environmental companion owner")
    rows = db.execute(
        "SELECT * FROM environmental_entitlement_companions WHERE entitlement_id=%s ORDER BY companion_id FOR UPDATE",
        (entitlement_id,),
    ).fetchall()
    results = []
    for row in rows:
        if (row["account_id"], row["owner_character_id"]) != (account_id, character_id):
            raise ValueError("Environmental companion snapshot changed ownership")
        if row["delivered_at_ms"] is not None:
            if (row["owner_xp"], row["experience_award"]) != (owner_xp, amount):
                raise ValueError("Environmental companion XP basis changed on retry")
            continue
        # Eligibility was frozen at completion. Moving a slot afterwards cannot
        # substitute a different recipient or erase this earned entitlement.
        recipient = db.execute(
            "SELECT linked FROM account_companions WHERE id=%s AND account_id=%s FOR UPDATE",
            (row["companion_id"], account_id),
        ).fetchone()
        if recipient is None or recipient["linked"] is not True:
            # Unlinking moves XP custody into a physical activation item. Do
            # not silently award the disconnected account row or another pet.
            raise ValueError(
                "Frozen companion XP recipient requires its linked custody"
            )
        xp = companions.advance_experience(
            db, account_id=account_id, companion_id=row["companion_id"], amount=amount
        )
        db.execute(
            "UPDATE environmental_entitlement_companions SET owner_xp=%s,experience_award=%s,delivered_at_ms=%s "
            "WHERE entitlement_id=%s AND companion_id=%s",
            (
                owner_xp,
                amount,
                int(store.clock() * 1000),
                entitlement_id,
                row["companion_id"],
            ),
        )
        results.append(
            dict(
                companion_id=row["companion_id"], owner_xp=owner_xp, award=amount, xp=xp
            )
        )
    packets = (
        [companions.refresh_packet(companions.collection(db, account_id))]
        if results
        else []
    )
    return dict(packets=packets, results=tuple(results))
