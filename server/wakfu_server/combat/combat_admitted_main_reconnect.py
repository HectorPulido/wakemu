"""Durable proof for a new transport selecting an already admitted company hero."""


def admitted_main_reconnect(
    db,
    store,
    account_id,
    generation,
    character_id,
    previous_character_id,
    *,
    selected=True,
    fight_id=None,
    previous_generation=None,
):
    """Validate identity replacement without admitting or altering any fighter.

    Selection preflight runs before the new session selects its character;
    subsequent callers require that exact selected lease. The frozen durable
    player set must equal the real saved company, excluding summons/sidekicks.
    The durable takeover transaction remains responsible for moving the lease.
    """
    if character_id == previous_character_id:
        return False
    lease = db.execute(
        "SELECT character_id FROM sessions WHERE account_id=%s AND generation=%s "
        "AND expires_at>%s",
        (account_id, generation, store.now()),
    ).fetchone()
    if lease is None or lease["character_id"] != (character_id if selected else None):
        return False
    roster = db.execute(
        "SELECT leader_id FROM account_hero_rosters WHERE account_id=%s",
        (account_id,),
    ).fetchone()
    if roster is None:
        return False
    members = {roster["leader_id"]}
    members.update(
        row["character_id"]
        for row in db.execute(
            "SELECT character_id FROM account_hero_slots WHERE account_id=%s",
            (account_id,),
        ).fetchall()
    )
    if not {character_id, previous_character_id} <= members:
        return False
    rows = db.execute(
        "SELECT p.fight_id,p.character_id,p.session_generation,p.team,"
        "c.map_id,c.instance_id,EXISTS(SELECT 1 FROM combat_pve_withdrawals w "
        "WHERE w.fight_id=p.fight_id AND w.account_id=p.account_id) AS withdrew "
        "FROM combat_fight_participants p JOIN combat_fights f ON f.id=p.fight_id "
        "JOIN characters c ON c.id=p.character_id AND c.account_id=p.account_id "
        "WHERE p.account_id=%s AND f.status IN ('placement','active') "
        "AND c.deleted_at IS NULL ORDER BY p.fight_id,p.character_id",
        (account_id,),
    ).fetchall()
    fights = {row["fight_id"] for row in rows}
    generations = {row["session_generation"] for row in rows}
    return bool(
        len(fights) == 1
        and (fight_id is None or fights == {fight_id})
        and {row["character_id"] for row in rows} == members
        and len(generations) == 1
        and generation not in generations
        and (previous_generation is None or generations == {previous_generation})
        and len({row["team"] for row in rows}) == 1
        and len({(row["map_id"], row["instance_id"]) for row in rows}) == 1
        and not any(row["withdrew"] for row in rows)
    )
