"""PostgreSQL fight identities and owned durable participants."""

from psycopg.pq import TransactionStatus


def _require_transaction(db):
    if db.info.transaction_status != TransactionStatus.INTRANS:
        raise ValueError("Fight membership requires an active transaction")


def _health_baseline(db, account_id, character_id):
    row = db.execute(
        "SELECT hp,max_hp,hp_damage,health_dead FROM characters "
        "WHERE account_id=%s AND id=%s AND deleted_at IS NULL FOR UPDATE",
        (account_id, character_id),
    ).fetchone()
    if row is None:
        raise ValueError("Fight participant character is unavailable")
    hp, maximum, damage, dead = (
        row["hp"],
        row["max_hp"],
        row["hp_damage"],
        row["health_dead"],
    )
    if (
        any(type(value) is not int for value in (hp, maximum, damage))
        or type(dead) is not bool
        or maximum <= 0
        or not 0 <= hp <= maximum
        or damage < 0
    ):
        raise ValueError("Invalid fight participant health baseline")
    return hp, maximum, damage, dead


def create(store, account_id, generation, character_id, *, team=0):
    if type(team) is not int or team not in (0, 1):
        raise ValueError("Invalid fight participant team")
    with store.connection() as db:
        store.lock_character(db, account_id, generation, character_id)
        baseline = _health_baseline(db, account_id, character_id)
        fight_id = db.execute(
            "INSERT INTO combat_fights(status) VALUES('placement') RETURNING id"
        ).fetchone()["id"]
        db.execute(
            "INSERT INTO combat_fight_participants"
            "(fight_id,character_id,account_id,team,session_generation,"
            "entry_hp,entry_max_hp,entry_hp_damage,entry_health_dead) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (fight_id, character_id, account_id, team, generation, *baseline),
        )
        return fight_id


def join_participant(
    store,
    db,
    account_id,
    generation,
    character_id,
    fight_id,
    *,
    target_character_id,
    team,
):
    """Persist one admitted player in an existing placement fight.

    Network/map/team/cell admission belongs to the shared fight registry. This
    storage boundary rechecks the live selected-character lease, the target's
    durable membership, same-team placement phase, and idempotent identity.
    """
    _require_transaction(db)
    if (
        type(team) is not int
        or team not in (0, 1)
        or type(fight_id) is not int
        or not 0 < fight_id < 2**31
        or type(target_character_id) is not int
        or target_character_id <= 0
    ):
        raise ValueError("Invalid shared fight participant")
    fight = db.execute(
        "SELECT status FROM combat_fights WHERE id=%s FOR UPDATE", (fight_id,)
    ).fetchone()
    if fight is None or fight["status"] != "placement":
        raise ValueError("Fight is not open for participant admission")
    store.lock_character(db, account_id, generation, character_id)
    baseline = _health_baseline(db, account_id, character_id)
    target = db.execute(
        "SELECT account_id,team FROM combat_fight_participants "
        "WHERE fight_id=%s AND character_id=%s FOR UPDATE",
        (fight_id, target_character_id),
    ).fetchone()
    if target is None or target["team"] != team:
        raise ValueError("Join target is not a durable same-team participant")
    if target["account_id"] == account_id:
        raise ValueError("Account already owns a fight participant")

    prior = db.execute(
        "SELECT fight_id,account_id,team,session_generation "
        "FROM combat_fight_participants WHERE character_id=%s "
        "AND fight_id=%s FOR UPDATE",
        (character_id, fight_id),
    ).fetchone()
    if prior is not None:
        if (
            prior["account_id"] == account_id
            and prior["team"] == team
            and prior["session_generation"] == generation
        ):
            return False
        raise ValueError("Conflicting durable fight participant")
    if db.execute(
        "SELECT 1 FROM combat_fight_participants p JOIN combat_fights f ON f.id=p.fight_id "
        "WHERE p.character_id=%s AND f.status IN ('placement','active') "
        "AND NOT EXISTS(SELECT 1 FROM combat_pve_withdrawals w "
        "WHERE w.fight_id=p.fight_id AND w.character_id=p.character_id) LIMIT 1",
        (character_id,),
    ).fetchone():
        raise ValueError("Character already has an active durable fight")
    if db.execute(
        "SELECT 1 FROM combat_fight_participants WHERE fight_id=%s AND account_id=%s LIMIT 1",
        (fight_id, account_id),
    ).fetchone():
        raise ValueError("Account already owns a fight participant")
    db.execute(
        "INSERT INTO combat_fight_participants"
        "(fight_id,character_id,account_id,team,session_generation,"
        "entry_hp,entry_max_hp,entry_hp_damage,entry_health_dead) "
        "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
        (fight_id, character_id, account_id, team, generation, *baseline),
    )
    return True


def finish(store, db, account_id, generation, character_id, fight_id):
    _require_transaction(db)
    row = db.execute(
        "SELECT f.status,p.session_generation FROM combat_fights f JOIN combat_fight_participants p ON p.fight_id=f.id "
        "WHERE f.id=%s AND p.character_id=%s AND p.account_id=%s FOR UPDATE OF f",
        (fight_id, character_id, account_id),
    ).fetchone()
    if (
        row is None
        or row["status"] == "aborted"
        or row["session_generation"] not in (None, generation)
    ):
        raise ValueError("Missing or aborted owned durable fight")
    store.lock_character(db, account_id, generation, character_id)
    db.execute("UPDATE combat_fights SET status='finished' WHERE id=%s", (fight_id,))


def settle_shared(store, account_id, generation, character_id, fight, settle):
    """Commit one shared result and all owner settlements atomically.

    Only the current lease of the finalizer is required. Other owners are
    authorized by their durable participant rows and recorded join generation,
    so a disconnected teammate does not lose a committed reward. ``settle`` is
    a trusted storage callback receiving ``(db, participant_rows, fight)`` and
    must apply all participant receipts using this same transaction.
    """
    if (
        not callable(settle)
        or getattr(fight, "phase", None) != "finished"
        or getattr(fight, "winner", None) not in (0, 1)
        or type(getattr(fight, "id", None)) is not int
        or not 0 < fight.id < 2**31
    ):
        raise ValueError("Invalid shared fight settlement")
    controlled = {
        actor.id: actor.owner_id for actor in fight.actors.values() if actor.controlled
    }
    if (
        not controlled
        or character_id not in controlled
        or controlled[character_id] != account_id
    ):
        raise ValueError("Finalizer is not a fight participant")
    with store.connection() as db:
        fight_row = db.execute(
            "SELECT status FROM combat_fights WHERE id=%s FOR UPDATE", (fight.id,)
        ).fetchone()
        if fight_row is None or fight_row["status"] not in (
            "placement",
            "active",
            "finished",
        ):
            raise ValueError("Shared fight is missing or terminal-aborted")
        finalizer = db.execute(
            "SELECT session_generation FROM combat_fight_participants "
            "WHERE fight_id=%s AND character_id=%s AND account_id=%s FOR UPDATE",
            (fight.id, character_id, account_id),
        ).fetchone()
        if finalizer is None or finalizer["session_generation"] != generation:
            raise ValueError("Finalizer no longer owns the durable fight lease")
        store.lock_character(db, account_id, generation, character_id)
        rows = tuple(
            db.execute(
                "SELECT p.character_id,p.account_id,p.team,p.session_generation,"
                "EXISTS(SELECT 1 FROM combat_pve_withdrawals w WHERE "
                "w.fight_id=p.fight_id AND w.character_id=p.character_id) AS withdrawn "
                "FROM combat_fight_participants p WHERE p.fight_id=%s "
                "ORDER BY p.character_id FOR UPDATE OF p",
                (fight.id,),
            )
        )
        for row in rows:
            locked = db.execute(
                "SELECT id FROM characters WHERE id=%s AND account_id=%s "
                "AND deleted_at IS NULL FOR UPDATE",
                (row["character_id"], row["account_id"]),
            ).fetchone()
            if locked is None:
                raise ValueError("Shared fight participant character is unavailable")
        durable = {row["character_id"]: row["account_id"] for row in rows}
        if durable != controlled:
            raise ValueError("Runtime and durable shared fight rosters differ")
        by_id = {actor.id: actor for actor in fight.actors.values()}
        if any(
            row["team"] != by_id[row["character_id"]].team
            or row["session_generation"] is None
            for row in rows
        ):
            raise ValueError("Shared fight participant authority is incomplete")
        if fight_row["status"] != "finished":
            db.execute(
                "UPDATE combat_fights SET status='finished' WHERE id=%s",
                (fight.id,),
            )
        return settle(db, rows, fight)


def activate(store, account_id, generation, character_id, fight_id):
    with store.connection() as db:
        row = db.execute(
            "SELECT status FROM combat_fights WHERE id=%s FOR UPDATE", (fight_id,)
        ).fetchone()
        if row is None or row["status"] not in ("placement", "active"):
            raise ValueError("Missing or terminal owned durable fight")
        store.lock_character(db, account_id, generation, character_id)
        result = db.execute(
            "UPDATE combat_fights f SET status='active' FROM combat_fight_participants p "
            "WHERE f.id=p.fight_id AND f.id=%s AND p.character_id=%s AND p.account_id=%s "
            "AND f.status IN ('placement','active') "
            "AND (p.session_generation IS NULL OR p.session_generation=%s)",
            (fight_id, character_id, account_id, generation),
        )
        if result.rowcount != 1:
            raise ValueError("Missing or terminal owned durable fight")


def takeover_participant(
    store,
    account_id,
    generation,
    character_id,
    fight_id,
    *,
    previous_generation,
):
    """Fence a reconnected owner onto its existing durable participant row."""
    if not isinstance(previous_generation, str) or not previous_generation:
        raise ValueError("Invalid previous combat participant generation")
    with store.connection() as db:
        row = db.execute(
            "SELECT f.status,p.session_generation,"
            "EXISTS(SELECT 1 FROM fight_health_exits e "
            "WHERE e.fight_id=f.id AND e.character_id=p.character_id "
            "AND e.return_acknowledged_at IS NOT NULL) AS return_acknowledged "
            "FROM combat_fights f "
            "JOIN combat_fight_participants p ON p.fight_id=f.id "
            "WHERE f.id=%s AND p.character_id=%s AND p.account_id=%s FOR UPDATE OF f,p",
            (fight_id, character_id, account_id),
        ).fetchone()
        if row is None or row["status"] not in ("placement", "active", "finished"):
            raise ValueError("Fight participant is unavailable for takeover")
        if row["status"] == "finished" and row["return_acknowledged"]:
            raise ValueError("Finished fight participant already acknowledged return")
        store.lock_character(db, account_id, generation, character_id)
        if row["session_generation"] == generation:
            return False
        if row["session_generation"] != previous_generation:
            raise ValueError("Stale durable combat participant generation")
        db.execute(
            "UPDATE combat_fight_participants SET session_generation=%s "
            "WHERE fight_id=%s AND character_id=%s AND account_id=%s",
            (generation, fight_id, character_id, account_id),
        )
        return True


def abort(
    store, account_id, character_id, fight_id, *, expected_generation=None, db=None
):
    """Cleanup only this durable identity; never mutate character or finished fight."""
    if db is None:
        with store.connection() as connection:
            return abort(
                store,
                account_id,
                character_id,
                fight_id,
                expected_generation=expected_generation,
                db=connection,
            )
    from psycopg.pq import TransactionStatus

    if db.info.transaction_status != TransactionStatus.INTRANS:
        raise ValueError("Fight abort requires an active transaction")
    query = (
        "UPDATE combat_fights f SET status='aborted' FROM combat_fight_participants p "
        "WHERE f.id=p.fight_id AND f.id=%s AND p.character_id=%s AND p.account_id=%s "
        "AND f.status IN ('placement','active')"
    )
    params = [fight_id, character_id, account_id]
    if expected_generation is not None:
        # NULL rows are legacy participants with no generation fence. Once a
        # takeover writes a concrete newer generation, an old finalizer cannot
        # abort that live owner's fight.
        query += " AND (p.session_generation IS NULL OR p.session_generation=%s)"
        params.append(expected_generation)
    return db.execute(query, tuple(params)).rowcount == 1
