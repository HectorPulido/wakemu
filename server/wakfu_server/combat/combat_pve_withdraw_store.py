"""Durable individual PvE surrender, preserving the live encounter outcome."""
from . import combat_health


def persist(
    store, session, character, original_fight, *, db=None, captured_departure_fight=None
):
    """Save authoritative wounds and exclusion receipt in one fight-first TX.

    ``original_fight`` must still have the participant's actual HP. The detached
    withdrawal candidate has zero fight HP only to retire it from combat and
    must never determine persisted wounds or death.
    """
    if db is None:
        with store.connection() as connection:
            return persist(
                store,
                session,
                character,
                original_fight,
                db=connection,
                captured_departure_fight=captured_departure_fight,
            )
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
    store.lock_character(
        db, session.account_id, session.generation, session.character_id
    )
    from .combat_terminal_metadata import registered_summon_actor_ids

    summons = registered_summon_actor_ids(original_fight)
    owned_ids = {
        actor.id
        for actor in original_fight.actors.values()
        if actor.controlled
        and actor.owner_id == session.account_id
        and actor.id not in summons
    }
    members = tuple(
        db.execute(
            "SELECT character_id,session_generation FROM combat_fight_participants "
            "WHERE fight_id=%s AND account_id=%s ORDER BY character_id FOR UPDATE",
            (original_fight.id, session.account_id),
        )
    )
    if {member["character_id"] for member in members} != owned_ids or any(
        member["session_generation"] != session.generation for member in members
    ):
        raise ValueError(
            "Withdrawal hero roster differs from frozen account participants"
        )
    characters = {}
    applied = False
    for member in members:
        identity = member["character_id"]
        source = (
            character
            if identity == session.character_id
            else store.character(session.account_id, identity, db)
        )
        health = combat_health.persist(
            store,
            session.account_id,
            session.generation,
            source,
            original_fight,
            reason="abort",
            db=db,
            session_character_id=session.character_id,
        )
        characters[identity] = health["character"]
        inserted = db.execute(
            "INSERT INTO combat_pve_withdrawals "
            "(fight_id,character_id,account_id,session_generation,created_at) "
            "VALUES(%s,%s,%s,%s,%s) ON CONFLICT(fight_id,character_id) DO NOTHING",
            (
                original_fight.id,
                identity,
                session.account_id,
                session.generation,
                store.now(),
            ),
        )
        applied = applied or inserted.rowcount == 1
    if captured_departure_fight is not None:
        if captured_departure_fight.id != original_fight.id:
            raise ValueError("Captured teardown belongs to another fight")
        from .combat_captured_roster_checkpoint import persist_captured_roster_updates

        persist_captured_roster_updates(
            db, captured_departure_fight, owner_ids=owned_ids
        )
        reset = getattr(
            captured_departure_fight, "native_captured_roster_updates", {}
        ).get(str(session.character_id))
        if reset is not None:
            characters[session.character_id] = {
                **characters[session.character_id],
                "captured_roster": reset,
            }
    return dict(
        character=characters[session.character_id],
        characters=characters,
        applied=applied,
    )


def _complete_owned_health_return(store, db, session, fight_id):
    """Finish only certified withdrawal health, once, inside its return TX.

    An abort receipt alone never revives a character. The matching account's
    complete ordinary withdrawal roster, selected lease and unchanged dead
    exit baseline establish the exploration continuation. Combat actors and
    encounter outcome remain untouched.
    """
    from wakfu_server import health_policy

    participants = tuple(
        db.execute(
            "SELECT character_id,session_generation FROM combat_fight_participants "
            "WHERE fight_id=%s AND account_id=%s ORDER BY character_id FOR UPDATE",
            (fight_id, session.account_id),
        )
    )
    withdrawals = tuple(
        db.execute(
            "SELECT character_id,session_generation,health_returned_at FROM combat_pve_withdrawals "
            "WHERE fight_id=%s AND account_id=%s ORDER BY character_id FOR UPDATE",
            (fight_id, session.account_id),
        )
    )
    member_ids = {row["character_id"] for row in participants}
    if (
        not member_ids
        or session.character_id not in member_ids
        or member_ids != {row["character_id"] for row in withdrawals}
        or any(row["session_generation"] != session.generation for row in withdrawals)
    ):
        raise ValueError("Withdrawal health return lacks the complete owned roster")
    withdrawal_by_id = {row["character_id"]: row for row in withdrawals}
    for member in participants:
        identity = member["character_id"]
        store.lock_character(
            db,
            session.account_id,
            session.generation,
            identity,
            selected=identity == session.character_id,
        )
        exit_row = db.execute(
            "SELECT reason,generation,created_at,return_acknowledged_at "
            "FROM fight_health_exits WHERE fight_id=%s AND character_id=%s FOR UPDATE",
            (fight_id, identity),
        ).fetchone()
        if (
            exit_row is None
            or exit_row["reason"] != "abort"
            or exit_row["generation"] != member["session_generation"]
        ):
            raise ValueError("Withdrawal health return lacks its original exit receipt")
        if withdrawal_by_id[identity]["health_returned_at"] is not None:
            continue
        character = store.character(session.account_id, identity, db)
        if character["health_dead"]:
            baseline = db.execute(
                "SELECT initial_hp,initial_damage,started_at,coefficient "
                "FROM character_regeneration WHERE character_id=%s FOR UPDATE",
                (identity,),
            ).fetchone()
            newer = db.execute(
                "SELECT 1 FROM fight_health_exits WHERE character_id=%s "
                "AND fight_id<>%s AND created_at>=%s LIMIT 1",
                (identity, fight_id, exit_row["created_at"]),
            ).fetchone()
            active = db.execute(
                "SELECT 1 FROM combat_fight_participants p JOIN combat_fights f ON f.id=p.fight_id "
                "WHERE p.character_id=%s AND p.fight_id<>%s AND f.status IN ('placement','active') "
                "AND NOT EXISTS(SELECT 1 FROM combat_pve_withdrawals w "
                "WHERE w.fight_id=p.fight_id AND w.character_id=p.character_id) LIMIT 1",
                (identity, fight_id),
            ).fetchone()
            if (
                character["hp"] != 0
                or baseline is None
                or baseline["initial_hp"] != 0
                or baseline["initial_damage"] != character["hp_damage"]
                or baseline["coefficient"] != 0
                or baseline["started_at"] != exit_row["created_at"]
                or newer is not None
                or active is not None
            ):
                raise ValueError(
                    "Dead withdrawal health no longer matches its exit baseline"
                )
            # Reuse the explicit Wakemu one-HP exploration policy only after
            # the owned withdrawal continuation, never a generic abort/tick.
            damage, dead = health_policy.recover_finished_return(
                character["max_hp"], character["hp_damage"], True
            )
            hp = health_policy.apply_damage(db, character, damage, dead)
            now = store.now()
            db.execute(
                "INSERT INTO character_regeneration(character_id,initial_hp,started_at,coefficient,last_at) "
                "VALUES(%s,%s,%s,1,%s) ON CONFLICT(character_id) DO UPDATE SET "
                "initial_hp=excluded.initial_hp,started_at=excluded.started_at,"
                "coefficient=excluded.coefficient,last_at=excluded.last_at",
                (identity, hp, now, now),
            )
        db.execute(
            "UPDATE combat_pve_withdrawals SET health_returned_at=%s "
            "WHERE fight_id=%s AND character_id=%s AND health_returned_at IS NULL",
            (store.now(), fight_id, identity),
        )


def acknowledge(store, session, fight_id):
    """Native return ACK frees only the withdrawn participant's UI receipt."""
    with store.connection() as db:
        db.execute("SELECT id FROM combat_fights WHERE id=%s FOR UPDATE", (fight_id,))
        store.lock_character(
            db, session.account_id, session.generation, session.character_id
        )
        row = db.execute(
            "UPDATE combat_pve_withdrawals SET returned_at=COALESCE(returned_at,%s) "
            "WHERE fight_id=%s AND account_id=%s "
            "AND session_generation=%s RETURNING character_id",
            (
                store.now(),
                fight_id,
                session.account_id,
                session.generation,
            ),
        ).fetchone()
        if row is None:
            raise ValueError("No owned PvE withdrawal continuation")
        _complete_owned_health_return(store, db, session, fight_id)
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
        db.execute(
            "UPDATE combat_pve_withdrawals SET session_generation=%s,"
            "returned_at=COALESCE(returned_at,%s) WHERE fight_id=%s AND account_id=%s "
            "AND session_generation=%s",
            (
                session.generation,
                store.now(),
                fight_id,
                session.account_id,
                previous_generation,
            ),
        )
        _complete_owned_health_return(store, db, session, fight_id)
        return store.character(session.account_id, session.character_id, db)


def recover_pending(store, session):
    """Complete interrupted receipts after registry retirement/process restart."""
    with store.connection() as db:
        pending = tuple(
            db.execute(
                "SELECT w.fight_id,w.session_generation FROM combat_pve_withdrawals w "
                "WHERE w.account_id=%s AND w.character_id=%s AND (w.returned_at IS NULL OR EXISTS("
                "SELECT 1 FROM combat_pve_withdrawals m JOIN fight_health_exits e "
                "ON e.fight_id=m.fight_id AND e.character_id=m.character_id "
                "JOIN characters c ON c.id=m.character_id "
                "JOIN character_regeneration r ON r.character_id=c.id "
                "WHERE m.fight_id=w.fight_id AND m.account_id=w.account_id "
                "AND e.reason='abort' AND m.health_returned_at IS NULL "
                "AND c.health_dead AND c.hp=0 AND r.initial_hp=0 AND r.coefficient=0 "
                "AND r.initial_damage=c.hp_damage AND r.started_at=e.created_at "
                "AND NOT EXISTS(SELECT 1 FROM fight_health_exits newer "
                "WHERE newer.character_id=c.id AND newer.fight_id<>w.fight_id "
                "AND newer.created_at>=e.created_at) "
                "AND NOT EXISTS(SELECT 1 FROM combat_fight_participants other "
                "JOIN combat_fights live ON live.id=other.fight_id "
                "WHERE other.character_id=c.id AND other.fight_id<>w.fight_id "
                "AND live.status IN ('placement','active') "
                "AND NOT EXISTS(SELECT 1 FROM combat_pve_withdrawals retired "
                "WHERE retired.fight_id=other.fight_id "
                "AND retired.character_id=other.character_id)))) "
                "ORDER BY w.fight_id",
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
                "session_generation=%s WHERE fight_id=%s "
                "AND account_id=%s AND session_generation=%s",
                (
                    store.now(),
                    session.generation,
                    row["fight_id"],
                    session.account_id,
                    row["session_generation"],
                ),
            )
            _complete_owned_health_return(store, db, session, row["fight_id"])
        return store.character(session.account_id, session.character_id, db)
