"""Atomic, lease-scoped fight-exit HP persistence without reward side effects."""
from . import health_store, health


def _schema(db):
    health_store.schema(db)
    db.execute(
        """CREATE TABLE IF NOT EXISTS fight_health_exits (
        generation TEXT NOT NULL, fight_id INTEGER NOT NULL,
        character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
        reason TEXT NOT NULL, created_at REAL NOT NULL,
        PRIMARY KEY(generation,fight_id,character_id))"""
    )


def persist(store, account_id, generation, character, fight, *, reason="return"):
    """Record HP once; duplicate callbacks preserve subsequent world HP/position.

    'return' requires a finished fight; 'abort' also handles placement/active
    disconnection. Session replacement or stale HP must never overwrite the
    newer owner's state. No rewards or fight phase changes occur here.
    """
    actor = fight.actors.get(character["id"])
    if (
        reason not in ("return", "abort")
        or actor is None
        or not actor.controlled
        or actor.owner_id != account_id
    ):
        raise ValueError("Invalid own fight health exit")
    if reason == "return" and fight.phase != "finished":
        raise ValueError("Fight has not finished")
    with store.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        _schema(db)
        saved = health_store._owned(store, db, account_id, generation, character["id"])
        if (
            db.execute(
                "SELECT reason FROM fight_health_exits WHERE generation=? AND fight_id=? AND character_id=?",
                (generation, fight.id, character["id"]),
            ).fetchone()
            is not None
        ):
            return dict(character=saved, applied=False)
        if saved["hp"] != character["hp"]:
            raise ValueError("Stale fight exit HP")
        if not 0 <= actor.hp <= actor.max_hp:
            raise ValueError("Invalid authoritative fight HP")
        from .equipment_stats import effective_character

        maximum = effective_character(saved)["max_hp"]
        # Existing native health policy: full stays full on levelup;
        # a wound preserves current HP, clamped if the maximum decreased.
        hp = maximum if actor.hp == actor.max_hp else min(actor.hp, maximum)
        coefficient = 1 if hp > 0 else 0
        now_ms = int(store.clock() * 1000)
        db.execute(
            "UPDATE characters SET hp=?,max_hp=? WHERE account_id=? AND id=?",
            (hp, maximum, account_id, character["id"]),
        )
        db.execute(
            "INSERT INTO character_regeneration VALUES(?,?,?,?,?) ON CONFLICT(character_id) DO UPDATE SET "
            "initial_hp=excluded.initial_hp,started_ms=excluded.started_ms,coefficient=excluded.coefficient,last_ms=excluded.last_ms",
            (character["id"], hp, now_ms, coefficient, now_ms),
        )
        db.execute(
            "INSERT INTO fight_health_exits VALUES(?,?,?,?,?)",
            (generation, fight.id, character["id"], reason, store.clock()),
        )
        return dict(
            character=store.character(account_id, character["id"], db),
            applied=True,
            coefficient=coefficient,
        )


def persist_aborted_fight(store, account_id, generation, character, fight):
    """Safe finally helper: damage survives disconnect; stale leases are ignored.

    Return {applied, character} on a valid/duplicate exit, otherwise None. The
    caller still releases its world/fight lease. This never grants rewards.
    """
    if character is None or fight is None or account_id is None or generation is None:
        return None
    try:
        return persist(store, account_id, generation, character, fight, reason="abort")
    except ValueError:
        return None
