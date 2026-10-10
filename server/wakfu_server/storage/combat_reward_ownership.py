"""Owned combat loot recipients under real main sessions, including heroes."""


def lock_recipient(store, db, account_id, generation, character_id, fight_id):
    """Fence a selected main or a durable same-company hero; never create leases.

    Inactive ordinary characters are not authorized by account ownership alone.
    A hero must still belong to the selected main's native company and both must
    be recorded in this finished fight with the same generation and team.
    """
    lease = db.execute(
        "SELECT character_id FROM sessions WHERE account_id=%s AND generation=%s "
        "AND expires_at>%s FOR UPDATE",
        (account_id, generation, store.now()),
    ).fetchone()
    if lease is None:
        raise ValueError("Combat loot recipient has no current account lease")
    main_id = lease["character_id"]
    if main_id == character_id:
        store.lock_character(db, account_id, generation, character_id)
        return
    roster = db.execute(
        "SELECT leader_id FROM account_hero_rosters WHERE account_id=%s FOR UPDATE",
        (account_id,),
    ).fetchone()
    hero = db.execute(
        "SELECT 1 FROM account_hero_slots WHERE account_id=%s AND character_id=%s",
        (account_id, character_id),
    ).fetchone()
    participants = db.execute(
        "SELECT p.character_id,p.team FROM combat_fight_participants p "
        "JOIN combat_fights f ON f.id=p.fight_id WHERE p.fight_id=%s AND "
        "p.account_id=%s AND p.session_generation=%s AND p.character_id=ANY(%s) "
        "AND f.status='finished'",
        (fight_id, account_id, generation, [main_id, character_id]),
    ).fetchall()
    if (
        roster is None
        or roster["leader_id"] != main_id
        or hero is None
        or {p["character_id"] for p in participants} != {main_id, character_id}
        or len({p["team"] for p in participants}) != 1
    ):
        raise ValueError("Combat loot recipient is not a frozen owned hero")
    store.lock_character(db, account_id, generation, character_id, selected=False)
