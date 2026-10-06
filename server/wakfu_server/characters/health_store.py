"""Session-scoped health persistence; no fixture HP enters owned state."""
from contextlib import nullcontext
from datetime import datetime, timezone
from psycopg.pq import TransactionStatus
import threading
import weakref
from wakfu_server import health, health_policy

_TICK_LOCK = threading.RLock()
_TICK_CLOCKS = weakref.WeakKeyDictionary()


def timestamp(now_ms):
    if type(now_ms) is not int:
        raise ValueError("Invalid regeneration clock")
    return datetime.fromtimestamp(now_ms / 1000, timezone.utc)


def _owned(store, db, account_id, generation, character_id):
    store.lock_character(db, account_id, generation, character_id)
    return store.character(account_id, character_id, db)


def initialize(
    store, account_id, generation, character_id, *, coefficient=0, now_ms=None, db=None
):
    """Reconcile effective maximum without erasing canonical wounds or death.

    Call on selection before sending initial HP; shared with build transitions.
    """
    now_ms = int(store.clock() * 1000) if now_ms is None else now_ms
    if db is not None and db.info.transaction_status != TransactionStatus.INTRANS:
        raise ValueError("Health initialization requires an active transaction")
    borrowed = db is not None
    with nullcontext(db) if borrowed else store.connection() as db:
        character = _owned(store, db, account_id, generation, character_id)
        from .equipment_stats import effective_character

        maximum = effective_character(character)["max_hp"]
        hp = health_policy.reconfigure(db, character, maximum)
        if hp == 0:
            coefficient = 0  # A dead character waits for explicit resurrection.
        health.packet(character_id, hp, coefficient)
        db.execute(
            "INSERT INTO character_regeneration(character_id,initial_hp,started_at,coefficient,last_at) VALUES(%s,%s,%s,%s,%s) ON CONFLICT(character_id) DO UPDATE SET "
            "initial_hp=excluded.initial_hp,started_at=excluded.started_at,coefficient=excluded.coefficient,last_at=excluded.last_at",
            (character_id, hp, timestamp(now_ms), coefficient, timestamp(now_ms)),
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
        character = _owned(store, db, account_id, generation, character_id)
        if character["hp"] != expected_hp or hp > character["max_hp"]:
            raise ValueError("Stale or out-of-range health")
        hp = health_policy.apply(db, character, hp)
        db.execute(
            "INSERT INTO character_regeneration(character_id,initial_hp,started_at,coefficient,last_at) VALUES(%s,%s,%s,%s,%s) ON CONFLICT(character_id) DO UPDATE SET "
            "initial_hp=excluded.initial_hp,started_at=excluded.started_at,coefficient=excluded.coefficient,last_at=excluded.last_at",
            (character_id, hp, timestamp(now_ms), coefficient, timestamp(now_ms)),
        )
        return store.character(account_id, character_id, db)


def tick(store, account_id, generation, character_id, expected_hp, *, now_ms=None):
    """Read-only until integer HP changes; keep the original fractional baseline.

    Returns a lightweight owned HP snapshot (id/account/breed/level/hp/max_hp),
    avoiding full Store.character hydration.
    Persistent last_ms records the last applied change. A per-Store high-water
    clock validates skipped observations in this process without writing persistent state
    for full/dead/stopped characters or sub-integer regeneration increments.
    """
    now_ms = int(store.clock() * 1000) if now_ms is None else now_ms
    if type(now_ms) is not int:
        raise ValueError("Invalid regeneration clock")
    with _TICK_LOCK, store.connection() as db:

        def evaluate():
            session = db.execute(
                "SELECT character_id FROM sessions WHERE account_id=%s AND generation=%s AND expires_at>%s",
                (account_id, generation, store.now()),
            ).fetchone()
            if session is None or session["character_id"] != character_id:
                raise ValueError("Invalid health session")
            row = db.execute(
                "SELECT id,account_id,breed,level,hp,max_hp,hp_damage,health_dead FROM characters WHERE id=%s AND account_id=%s",
                (character_id, account_id),
            ).fetchone()
            if row is None:
                raise ValueError("Invalid health character")
            character = dict(row)
            totals = db.execute(
                "SELECT xp FROM character_progression WHERE character_id=%s",
                (character_id,),
            ).fetchone()
            wallet = db.execute(
                "SELECT kamas FROM account_wallets WHERE account_id=%s", (account_id,)
            ).fetchone()
            if totals is not None:
                from wakfu_server.progression import level_xp

                character.update(
                    xp=totals["xp"],
                    kamas=wallet["kamas"] if wallet is not None else 0,
                )
            if character["hp"] != expected_hp:
                raise ValueError("Stale health update")
            state = db.execute(
                "SELECT * FROM character_regeneration WHERE character_id=%s",
                (character_id,),
            ).fetchone()
            if state is None:
                raise ValueError("Invalid regeneration clock")
            state["started_ms"] = int(state["started_at"].timestamp() * 1000)
            state["last_ms"] = int(state["last_at"].timestamp() * 1000)
            signature = (
                generation,
                state["initial_hp"],
                state["initial_damage"],
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
            damage = character["hp_damage"]
            if not character["health_dead"] and state["coefficient"]:
                elapsed = now_ms - state["started_ms"]
                gained = (
                    state["coefficient"] * elapsed + health.REGEN_DENOMINATOR_MS // 2
                ) // health.REGEN_DENOMINATOR_MS
                damage = max(0, state["initial_damage"] - gained)
            hp = health_policy.visible(
                character["max_hp"], damage, character["health_dead"]
            )
            return character, state, signature, hp, damage

        character, state, signature, hp, damage = evaluate()
        if damage != character["hp_damage"]:
            store.lock_character(db, account_id, generation, character_id)
            character, state, signature, hp, damage = evaluate()
            if damage != character["hp_damage"]:
                hp = health_policy.apply_damage(
                    db, character, damage, character["health_dead"]
                )
                db.execute(
                    "UPDATE character_regeneration SET last_at=%s WHERE character_id=%s",
                    (timestamp(now_ms), character_id),
                )
                character["hp"] = hp
                character["hp_damage"] = damage
        _TICK_CLOCKS[store][(account_id, character_id)] = (signature, now_ms)
        return character
