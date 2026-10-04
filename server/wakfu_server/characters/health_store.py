"""Session-scoped health persistence; no fixture HP enters owned state."""
import threading
import weakref
from wakfu_server import health

_TICK_LOCK = threading.RLock()
_TICK_CLOCKS = weakref.WeakKeyDictionary()


def schema(db):
    db.execute(
        """CREATE TABLE IF NOT EXISTS character_regeneration (
        character_id INTEGER PRIMARY KEY REFERENCES characters(id),
        initial_hp INTEGER NOT NULL, started_ms INTEGER NOT NULL,
        coefficient INTEGER NOT NULL, last_ms INTEGER NOT NULL)"""
    )


def _owned(store, db, account_id, generation, character_id):
    session = db.execute(
        "SELECT character_id FROM sessions WHERE account_id=? AND generation=? AND expires_at>?",
        (account_id, generation, store.clock()),
    ).fetchone()
    if session is None or session["character_id"] != character_id:
        raise ValueError("Invalid health session")
    return store.character(account_id, character_id, db)


def initialize(
    store, account_id, generation, character_id, *, coefficient=0, now_ms=None
):
    """Repair bare maximum; a previously full character remains full.

    Call on selection before sending initial HP. Incomplete equipment/passive
    HP bonuses must be implemented before enabling them in the local world.
    """
    now_ms = int(store.clock() * 1000) if now_ms is None else now_ms
    with store.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        schema(db)
        character = _owned(store, db, account_id, generation, character_id)
        from .equipment_stats import effective_character

        maximum = effective_character(character)["max_hp"]
        hp = (
            maximum
            if character["hp"] == character["max_hp"]
            else min(maximum, max(0, character["hp"]))
        )
        if hp == 0:
            coefficient = 0  # A dead character waits for explicit resurrection.
        health.packet(character_id, hp, coefficient)
        db.execute(
            "UPDATE characters SET hp=?,max_hp=? WHERE id=? AND account_id=?",
            (hp, maximum, character_id, account_id),
        )
        db.execute(
            "INSERT INTO character_regeneration VALUES(?,?,?,?,?) ON CONFLICT(character_id) DO UPDATE SET "
            "initial_hp=excluded.initial_hp,started_ms=excluded.started_ms,coefficient=excluded.coefficient,last_ms=excluded.last_ms",
            (character_id, hp, now_ms, coefficient, now_ms),
        )
        return store.character(account_id, character_id, db)


def sync(
    store,
    account_id,
    generation,
    character_id,
    expected_hp,
    hp,
    *,
    coefficient=0,
    now_ms=None
):
    """Set combat damage/healing or regeneration policy with prior-HP CAS."""
    now_ms = int(store.clock() * 1000) if now_ms is None else now_ms
    health.packet(character_id, hp, coefficient)
    with store.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        schema(db)
        character = _owned(store, db, account_id, generation, character_id)
        if character["hp"] != expected_hp or hp > character["max_hp"]:
            raise ValueError("Stale or out-of-range health")
        db.execute(
            "UPDATE characters SET hp=? WHERE id=? AND account_id=? AND hp=?",
            (hp, character_id, account_id, expected_hp),
        )
        db.execute(
            "INSERT INTO character_regeneration VALUES(?,?,?,?,?) ON CONFLICT(character_id) DO UPDATE SET "
            "initial_hp=excluded.initial_hp,started_ms=excluded.started_ms,coefficient=excluded.coefficient,last_ms=excluded.last_ms",
            (character_id, hp, now_ms, coefficient, now_ms),
        )
        return store.character(account_id, character_id, db)


def tick(store, account_id, generation, character_id, expected_hp, *, now_ms=None):
    """Read-only until integer HP changes; keep the original fractional baseline.

    Returns a lightweight owned HP snapshot (id/account/breed/level/hp/max_hp),
    avoiding Store.character hydration, which performs inventory initialization.
    Persistent last_ms records the last applied change. A per-Store high-water
    clock validates skipped observations in this process without writing SQLite
    for full/dead/stopped characters or sub-integer regeneration increments.
    """
    now_ms = int(store.clock() * 1000) if now_ms is None else now_ms
    if type(now_ms) is not int:
        raise ValueError("Invalid regeneration clock")
    with _TICK_LOCK, store.connection() as db:

        def evaluate():
            session = db.execute(
                "SELECT character_id FROM sessions WHERE account_id=? AND generation=? AND expires_at>?",
                (account_id, generation, store.clock()),
            ).fetchone()
            if session is None or session["character_id"] != character_id:
                raise ValueError("Invalid health session")
            row = db.execute(
                "SELECT id,account_id,breed,level,hp,max_hp FROM characters WHERE id=? AND account_id=?",
                (character_id, account_id),
            ).fetchone()
            if row is None:
                raise ValueError("Invalid health character")
            character = dict(row)
            totals = db.execute(
                "SELECT xp,kamas FROM character_progression WHERE character_id=?",
                (character_id,),
            ).fetchone()
            wallet = db.execute(
                "SELECT kamas FROM account_wallets WHERE account_id=?", (account_id,)
            ).fetchone()
            if totals is not None:
                from wakfu_server.progression import level_xp

                character.update(
                    xp=max(totals["xp"], level_xp(character["level"])),
                    kamas=wallet["kamas"] if wallet is not None else totals["kamas"],
                )
            if character["hp"] != expected_hp:
                raise ValueError("Stale health update")
            state = db.execute(
                "SELECT * FROM character_regeneration WHERE character_id=?",
                (character_id,),
            ).fetchone()
            if state is None:
                raise ValueError("Invalid regeneration clock")
            signature = (
                generation,
                state["initial_hp"],
                state["started_ms"],
                state["coefficient"],
            )
            clocks = _TICK_CLOCKS.setdefault(store, {})
            previous = clocks.get((account_id, character_id))
            minimum = state["last_ms"]
            if previous is not None and previous[0] == signature:
                minimum = max(minimum, previous[1])
            if now_ms < minimum:
                raise ValueError("Invalid regeneration clock")
            if character["hp"] in (0, character["max_hp"]) or state["coefficient"] == 0:
                hp = character["hp"]
            else:
                hp = health.regenerated(
                    state["initial_hp"],
                    character["max_hp"],
                    now_ms - state["started_ms"],
                    state["coefficient"],
                )
            return character, state, signature, hp

        character, state, signature, hp = evaluate()
        if hp != character["hp"]:
            # Re-read under a write lock: combat healing/damage, generation or
            # regeneration policy may have changed since the read-only probe.
            db.execute("BEGIN IMMEDIATE")
            character, state, signature, hp = evaluate()
            if hp != character["hp"]:
                result = db.execute(
                    "UPDATE characters SET hp=? WHERE id=? AND account_id=? AND hp=?",
                    (hp, character_id, account_id, expected_hp),
                )
                if result.rowcount != 1:
                    raise ValueError("Stale health update")
                db.execute(
                    "UPDATE character_regeneration SET last_ms=? WHERE character_id=?",
                    (now_ms, character_id),
                )
                character["hp"] = hp
        _TICK_CLOCKS[store][(account_id, character_id)] = (signature, now_ms)
        return character
