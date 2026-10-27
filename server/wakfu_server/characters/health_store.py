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
    store,
    account_id,
    generation,
    character_id,
    *,
    coefficient=0,
    exploration=False,
    now_ms=None,
    db=None,
):
    """Reconcile effective maximum without erasing canonical wounds or death.

    Call on selection before sending initial HP; shared with build transitions.
    """
    now_ms = int(store.clock() * 1000) if now_ms is None else now_ms
    if type(exploration) is not bool or (exploration and coefficient != 0):
        raise ValueError("Invalid exploration regeneration policy")
    if db is not None and db.info.transaction_status != TransactionStatus.INTRANS:
        raise ValueError("Health initialization requires an active transaction")
    borrowed = db is not None
    with nullcontext(db) if borrowed else store.connection() as db:
        character = _owned(store, db, account_id, generation, character_id)
        from wakfu_server.equipment_hp_lifecycle import reconcile_selected_build

        reconcile_selected_build(db, character)
        character = store.character(account_id, character_id, db)
        from .equipment_stats import effective_character

        maximum = effective_character(character, include_consumable_buffs=True)[
            "max_hp"
        ]
        if exploration:
            from .captured_roster_recovery import reconcile_aborted

            if reconcile_aborted(db, character):
                character = store.character(account_id, character_id, db)
            from .acknowledged_return_health import reconcile

            character = reconcile(db, character, maximum)
        hp = health_policy.reconfigure(db, character, maximum)
        if exploration:
            coefficient = health.exploration_coefficient(maximum, hp)
        if hp == 0 and character["health_dead"]:
            coefficient = 0  # A dead character waits for explicit resurrection.
        health.packet(character_id, hp, coefficient)
        db.execute(
            "INSERT INTO character_regeneration(character_id,initial_hp,started_at,coefficient,last_at) VALUES(%s,%s,%s,%s,%s) ON CONFLICT(character_id) DO UPDATE SET "
            "initial_hp=excluded.initial_hp,started_at=excluded.started_at,coefficient=excluded.coefficient,last_at=excluded.last_at",
            (character_id, hp, timestamp(now_ms), coefficient, timestamp(now_ms)),
        )
        character = store.character(account_id, character_id, db)
        from wakfu_server.territory_bonuses import reconcile_owned

        return reconcile_owned(store, account_id, generation, character, db=db)


def sync(
    store,
    account_id,
    generation,
    character_id,
    expected_hp,
    hp,
    *,
    coefficient=0,
    now_ms=None,
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
    """Tick the selected actor through the unchanged owned regeneration clock."""
    return _tick_owned(
        store,
        account_id,
        generation,
        character_id,
        expected_hp,
        selected_main_id=character_id,
        now_ms=now_ms,
    )


def _tick_owned(
    store,
    account_id,
    generation,
    character_id,
    expected_hp,
    *,
    selected_main_id,
    now_ms=None,
    db=None,
):
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
    with _TICK_LOCK, nullcontext(db) if db is not None else store.connection() as db:

        def evaluate():
            session = db.execute(
                "SELECT character_id FROM sessions WHERE account_id=%s AND generation=%s AND expires_at>%s",
                (account_id, generation, store.now()),
            ).fetchone()
            if session is None or session["character_id"] != selected_main_id:
                raise ValueError("Invalid health session")
            if character_id != selected_main_id:
                from wakfu_server.heroes import session_authorized

                if not session_authorized(
                    db,
                    dict(
                        id=character_id,
                        account_id=account_id,
                        selected_character_id=selected_main_id,
                    ),
                ):
                    raise ValueError("Character is not an active owned health hero")
            row = db.execute(
                "SELECT id,account_id,breed,level,hp,max_hp,hp_damage,health_dead,hp_zero_valid FROM characters WHERE id=%s AND account_id=%s AND deleted_at IS NULL",
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
                character["max_hp"],
                damage,
                character["health_dead"],
                character["hp_zero_valid"],
            )
            return character, state, signature, hp, damage

        character, state, signature, hp, damage = evaluate()
        if damage != character["hp_damage"]:
            store.lock_character(
                db,
                account_id,
                generation,
                character_id,
                selected=(character_id == selected_main_id),
            )
            character, state, signature, hp, damage = evaluate()
            if damage != character["hp_damage"]:
                hp = health_policy.apply_damage(
                    db,
                    character,
                    damage,
                    character["health_dead"],
                    hp_zero_valid=(
                        character["hp_zero_valid"]
                        and damage >= character["max_hp"]
                        and not character["health_dead"]
                    ),
                )
                db.execute(
                    "UPDATE character_regeneration SET last_at=%s WHERE character_id=%s",
                    (timestamp(now_ms), character_id),
                )
                character["hp"] = hp
                character["hp_damage"] = damage
        _TICK_CLOCKS[store][(account_id, character_id)] = (signature, now_ms)
        character["regeneration_coefficient"] = state["coefficient"]
        return character


def _healthy_company(
    store, db, account_id, generation, main_character_id, expected_hp, now_ms
):
    """A single read-only no-op proof; every mutable case uses the locked path."""
    rows = db.execute(
        "WITH lease AS ("
        " SELECT s.character_id,r.leader_id FROM sessions s "
        " LEFT JOIN account_hero_rosters r ON r.account_id=s.account_id "
        " WHERE s.account_id=%s AND s.generation=%s AND s.expires_at>%s"
        "), members AS ("
        " SELECT character_id AS member_id,character_id AS main_id,leader_id FROM lease "
        " UNION ALL SELECT h.character_id,l.character_id,l.leader_id "
        " FROM lease l JOIN account_hero_slots h ON h.account_id=%s"
        ") SELECT m.member_id,m.main_id,m.leader_id,c.id,c.account_id,c.hp,c.max_hp,"
        " c.hp_damage,c.health_dead,c.hp_zero_valid,r.initial_hp,r.initial_damage,"
        " r.started_at,r.last_at,r.coefficient FROM members m "
        " LEFT JOIN characters c ON c.id=m.member_id AND c.account_id=%s AND c.deleted_at IS NULL "
        " LEFT JOIN character_regeneration r ON r.character_id=c.id ORDER BY m.member_id",
        (account_id, generation, store.now(), account_id, account_id),
    ).fetchall()
    from wakfu_server.heroes import NATIVE_HERO_CAP

    ids = [row["member_id"] for row in rows]
    if (
        not rows
        or len(rows) > NATIVE_HERO_CAP + 1
        or len(set(ids)) != len(ids)
        or main_character_id not in ids
    ):
        return False
    clocks = _TICK_CLOCKS.get(store, {})
    observed = []
    for row in rows:
        if (
            row["main_id"] != main_character_id
            or row["leader_id"] not in (None, main_character_id)
            or row["id"] != row["member_id"]
            or row["account_id"] != account_id
            or row["started_at"] is None
            or row["last_at"] is None
            or row["initial_damage"] is None
            or row["coefficient"] is None
            or (row["id"] == main_character_id and row["hp"] != expected_hp)
            or not (row["health_dead"] or row["hp"] == row["max_hp"])
        ):
            return False
        if (
            health_policy.visible(
                row["max_hp"],
                row["hp_damage"],
                row["health_dead"],
                row["hp_zero_valid"],
            )
            != row["hp"]
        ):
            return False
        started_ms = int(row["started_at"].timestamp() * 1000)
        signature = (
            generation,
            row["initial_hp"],
            row["initial_damage"],
            started_ms,
            row["coefficient"],
        )
        minimum = int(row["last_at"].timestamp() * 1000)
        previous = clocks.get((account_id, row["id"]))
        if previous is not None and previous[0] == signature:
            minimum = max(minimum, previous[1])
        if now_ms < minimum:
            raise ValueError("Invalid regeneration clock")
        damage = row["hp_damage"]
        if not row["health_dead"] and row["coefficient"]:
            gained = (
                row["coefficient"] * (now_ms - started_ms)
                + health.REGEN_DENOMINATOR_MS // 2
            ) // health.REGEN_DENOMINATOR_MS
            damage = max(0, row["initial_damage"] - gained)
        if damage != row["hp_damage"]:
            return False  # A stale/inconsistent baseline needs the locked evaluator.
        observed.append((row["id"], signature))
    for identity, signature in observed:
        _TICK_CLOCKS.setdefault(store, {})[(account_id, identity)] = (signature, now_ms)
    return True


def tick_company(
    store,
    account_id,
    generation,
    main_character_id,
    expected_hp,
    *,
    now_ms=None,
):
    """Tick only the selected main and its current same-location owned heroes.

    Freeze the lease/roster before health rows, matching company mutation order.
    Reuse the selected actor's exact regeneration evaluator; never change maps,
    selected identity, wounds policy, or a dead actor's resurrection state.
    """
    now_ms = int(store.clock() * 1000) if now_ms is None else now_ms
    if type(now_ms) is not int:
        raise ValueError("Invalid regeneration clock")
    with _TICK_LOCK, store.connection() as db:
        if _healthy_company(
            store, db, account_id, generation, main_character_id, expected_hp, now_ms
        ):
            return ()
        db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account_id,))
        store.lock_character(db, account_id, generation, main_character_id)
        roster = db.execute(
            "SELECT leader_id FROM account_hero_rosters WHERE account_id=%s FOR UPDATE",
            (account_id,),
        ).fetchone()
        if roster is not None and roster["leader_id"] != main_character_id:
            raise ValueError("Selected health actor differs from active company")
        slots = db.execute(
            "SELECT character_id FROM account_hero_slots WHERE account_id=%s "
            "ORDER BY slot FOR UPDATE",
            (account_id,),
        ).fetchall()
        identities = sorted(
            {main_character_id, *(row["character_id"] for row in slots)}
        )
        if len(slots) > 2 or len(identities) != len(slots) + 1:
            raise ValueError("Invalid active health company")
        members = db.execute(
            "SELECT id,hp,max_hp,health_dead,map_id,instance_id FROM characters "
            "WHERE account_id=%s AND id=ANY(%s) AND deleted_at IS NULL ORDER BY id FOR UPDATE",
            (account_id, identities),
        ).fetchall()
        if [row["id"] for row in members] != identities:
            raise ValueError("Unavailable owned health company member")
        main = next(row for row in members if row["id"] == main_character_id)
        if main["hp"] != expected_hp:
            raise ValueError("Stale health update")
        from wakfu_server.heroes import _outside_combat

        try:
            _outside_combat(db, identities)
        except ValueError:
            return ()  # A durable live fight can precede this socket's local attachment.
        updates = []
        for member in members:
            if (member["map_id"], member["instance_id"]) != (
                main["map_id"],
                main["instance_id"],
            ):
                continue  # A pending hero return is not repaired by an HP tick.
            clock = db.execute(
                "SELECT coefficient FROM character_regeneration WHERE character_id=%s",
                (member["id"],),
            ).fetchone()
            start = (
                not member["health_dead"]
                and 0 < member["hp"] < member["max_hp"]
                and (clock is None or clock["coefficient"] == 0)
            )
            if clock is None or start:
                coefficient = (
                    health.exploration_coefficient(member["max_hp"], member["hp"])
                    if start
                    else 0
                )
                db.execute(
                    "INSERT INTO character_regeneration(character_id,initial_hp,started_at,coefficient,last_at) "
                    "VALUES(%s,%s,%s,%s,%s) ON CONFLICT(character_id) DO UPDATE SET "
                    "initial_hp=excluded.initial_hp,started_at=excluded.started_at,"
                    "coefficient=excluded.coefficient,last_at=excluded.last_at",
                    (
                        member["id"],
                        member["hp"],
                        timestamp(now_ms),
                        coefficient,
                        timestamp(now_ms),
                    ),
                )
            saved = _tick_owned(
                store,
                account_id,
                generation,
                member["id"],
                member["hp"],
                selected_main_id=main_character_id,
                now_ms=now_ms,
                db=db,
            )
            updates.append(
                dict(
                    saved,
                    previous_hp=member["hp"],
                    health_changed=(saved["hp"] != member["hp"] or start),
                )
            )
        return tuple(updates)
