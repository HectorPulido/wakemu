"""Durable individual PvE surrender, preserving the live encounter outcome."""
from . import combat_health


def persist(store, session, character, original_fight, *, db=None):
    """Save authoritative wounds and exclusion receipt in one fight-first TX.

    ``original_fight`` must still have the participant's actual HP. The detached
    withdrawal candidate has zero fight HP only to retire it from combat and
    must never determine persisted wounds or death.
    """
    if db is None:
        with store.connection() as connection:
            return persist(store, session, character, original_fight, db=connection)
    from psycopg.pq import TransactionStatus

    if db.info.transaction_status != TransactionStatus.INTRANS:
        raise ValueError("PvE withdrawal requires an active transaction")
    row = db.execute(
        "SELECT status FROM combat_fights WHERE id=%s FOR UPDATE",
        (original_fight.id,),
    ).fetchone()
    if row is None or row["status"] not in ("placement", "active"):
        raise ValueError("PvE encounter is no longer active")
    participant = db.execute(
        "SELECT session_generation FROM combat_fight_participants "
        "WHERE fight_id=%s AND character_id=%s AND account_id=%s FOR UPDATE",
        (original_fight.id, session.character_id, session.account_id),
    ).fetchone()
    if participant is None or participant["session_generation"] != session.generation:
        raise ValueError("PvE withdrawal has a stale durable participant")
    health = combat_health.persist(
        store,
        session.account_id,
        session.generation,
        character,
        original_fight,
        reason="abort",
        db=db,
    )
    inserted = db.execute(
        "INSERT INTO combat_pve_withdrawals "
        "(fight_id,character_id,account_id,session_generation,created_at) "
        "VALUES(%s,%s,%s,%s,%s) ON CONFLICT(fight_id,character_id) DO NOTHING",
        (
            original_fight.id,
            session.character_id,
            session.account_id,
            session.generation,
            store.now(),
        ),
    )
    return dict(character=health["character"], applied=inserted.rowcount == 1)


def acknowledge(store, session, fight_id):
    """Native return ACK frees only the withdrawn participant's UI receipt."""
    with store.connection() as db:
        db.execute("SELECT id FROM combat_fights WHERE id=%s FOR UPDATE", (fight_id,))
        store.lock_character(
            db, session.account_id, session.generation, session.character_id
        )
        row = db.execute(
            "UPDATE combat_pve_withdrawals SET returned_at=COALESCE(returned_at,%s) "
            "WHERE fight_id=%s AND character_id=%s AND account_id=%s "
            "AND session_generation=%s RETURNING character_id",
            (
                store.now(),
                fight_id,
                session.character_id,
                session.account_id,
                session.generation,
            ),
        ).fetchone()
        if row is None:
            raise ValueError("No owned PvE withdrawal continuation")
        return store.character(session.account_id, session.character_id, db)


def recover(store, session, fight_id, previous_generation):
    """Bind an interrupted withdrawal to its replacement selected lease only.

    This is a return to exploration, never takeover/resurrection of a combat.
    The historical participant generation and health receipt remain unchanged.
    """
    with store.connection() as db:
        db.execute("SELECT id FROM combat_fights WHERE id=%s FOR UPDATE", (fight_id,))
        store.lock_character(
            db, session.account_id, session.generation, session.character_id
        )
        row = db.execute(
            "UPDATE combat_pve_withdrawals SET session_generation=%s,"
            "returned_at=COALESCE(returned_at,%s) WHERE fight_id=%s "
            "AND character_id=%s AND account_id=%s AND session_generation=%s "
            "RETURNING character_id",
            (
                session.generation,
                store.now(),
                fight_id,
                session.character_id,
                session.account_id,
                previous_generation,
            ),
        ).fetchone()
        if row is None:
            raise ValueError("No matching interrupted PvE withdrawal")
        return store.character(session.account_id, session.character_id, db)


def recover_pending(store, session):
    """Complete interrupted receipts after registry retirement/process restart."""
    with store.connection() as db:
        pending = tuple(
            db.execute(
                "SELECT fight_id,session_generation FROM combat_pve_withdrawals "
                "WHERE account_id=%s AND character_id=%s AND returned_at IS NULL "
                "ORDER BY fight_id",
                (session.account_id, session.character_id),
            )
        )
        for row in pending:
            db.execute(
                "SELECT id FROM combat_fights WHERE id=%s FOR UPDATE",
                (row["fight_id"],),
            )
        store.lock_character(
            db, session.account_id, session.generation, session.character_id
        )
        if not pending:
            return None
        for row in pending:
            db.execute(
                "UPDATE combat_pve_withdrawals SET returned_at=COALESCE(returned_at,%s),"
                "session_generation=%s WHERE fight_id=%s AND character_id=%s "
                "AND account_id=%s AND session_generation=%s",
                (
                    store.now(),
                    session.generation,
                    row["fight_id"],
                    session.character_id,
                    session.account_id,
                    row["session_generation"],
                ),
            )
        return store.character(session.account_id, session.character_id, db)
