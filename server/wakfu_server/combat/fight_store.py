"""PostgreSQL fight identities and owned durable participants."""


def create(store, account_id, generation, character_id, *, team=0):
    if type(team) is not int or team not in (0, 1):
        raise ValueError("Invalid fight participant team")
    with store.connection() as db:
        store.lock_character(db, account_id, generation, character_id)
        fight_id = db.execute(
            "INSERT INTO combat_fights(status) VALUES('placement') RETURNING id"
        ).fetchone()["id"]
        db.execute(
            "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team) "
            "VALUES(%s,%s,%s,%s)",
            (fight_id, character_id, account_id, team),
        )
        return fight_id


def finish(store, db, account_id, generation, character_id, fight_id):
    store.lock_character(db, account_id, generation, character_id)
    row = db.execute(
        "SELECT f.status FROM combat_fights f JOIN combat_fight_participants p ON p.fight_id=f.id "
        "WHERE f.id=%s AND p.character_id=%s AND p.account_id=%s FOR UPDATE OF f",
        (fight_id, character_id, account_id),
    ).fetchone()
    if row is None or row["status"] == "aborted":
        raise ValueError("Missing or aborted owned durable fight")
    db.execute("UPDATE combat_fights SET status='finished' WHERE id=%s", (fight_id,))


def activate(store, account_id, generation, character_id, fight_id):
    with store.connection() as db:
        store.lock_character(db, account_id, generation, character_id)
        result = db.execute(
            "UPDATE combat_fights f SET status='active' FROM combat_fight_participants p "
            "WHERE f.id=p.fight_id AND f.id=%s AND p.character_id=%s AND p.account_id=%s "
            "AND f.status IN ('placement','active')",
            (fight_id, character_id, account_id),
        )
        if result.rowcount != 1:
            raise ValueError("Missing or terminal owned durable fight")


def abort(store, account_id, character_id, fight_id, *, db=None):
    """Cleanup only this durable identity; never mutate character or finished fight."""
    if db is None:
        with store.connection() as connection:
            return abort(store, account_id, character_id, fight_id, db=connection)
    from psycopg.pq import TransactionStatus

    if db.info.transaction_status != TransactionStatus.INTRANS:
        raise ValueError("Fight abort requires an active transaction")
    return (
        db.execute(
            "UPDATE combat_fights f SET status='aborted' FROM combat_fight_participants p "
            "WHERE f.id=p.fight_id AND f.id=%s AND p.character_id=%s AND p.account_id=%s "
            "AND f.status IN ('placement','active')",
            (fight_id, character_id, account_id),
        ).rowcount
        == 1
    )
