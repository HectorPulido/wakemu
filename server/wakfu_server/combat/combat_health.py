"""Atomic, lease-scoped fight-exit HP persistence without reward side effects."""
from . import health_store, health


def persist(
    store, account_id, generation, character, fight, *, reason="return", db=None
):
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
    if db is None:
        with store.connection() as connection:
            return persist(
                store,
                account_id,
                generation,
                character,
                fight,
                reason=reason,
                db=connection,
            )
    from psycopg.pq import TransactionStatus

    if db.info.transaction_status != TransactionStatus.INTRANS:
        raise ValueError("Fight health persistence requires an active transaction")
    saved = health_store._owned(store, db, account_id, generation, character["id"])
    if (
        db.execute(
            "SELECT reason FROM fight_health_exits WHERE fight_id=%s AND character_id=%s",
            (fight.id, character["id"]),
        ).fetchone()
        is not None
    ):
        return dict(character=saved, applied=False)
    if (
        db.execute(
            "SELECT character_id FROM combat_fight_participants WHERE fight_id=%s AND character_id=%s AND account_id=%s",
            (fight.id, character["id"], account_id),
        ).fetchone()
        is None
    ):
        raise ValueError("Missing owned durable fight participant")
    if saved["hp"] != character["hp"]:
        raise ValueError("Stale fight exit HP")
    if not 0 <= actor.hp <= actor.max_hp:
        raise ValueError("Invalid authoritative fight HP")
    from .equipment_stats import effective_character

    maximum = effective_character(saved)["max_hp"]
    from wakfu_server.health_policy import visible

    # Translate the fight's wound delta, rather than its temporary maximum,
    # back to the persisted configuration. Preserve pre-existing hidden wounds.
    initial_wound = character["max_hp"] - character["hp"]
    final_wound = actor.max_hp - actor.hp
    damage = max(0, saved["hp_damage"] + final_wound - initial_wound)
    dead = actor.hp == 0
    hp = visible(maximum, damage, dead)
    coefficient = 1 if hp > 0 else 0
    now = store.now()
    db.execute(
        "UPDATE characters SET hp=%s,max_hp=%s,hp_damage=%s,health_dead=%s "
        "WHERE account_id=%s AND id=%s",
        (hp, maximum, damage, dead, account_id, character["id"]),
    )
    db.execute(
        "INSERT INTO character_regeneration(character_id,initial_hp,started_at,coefficient,last_at) VALUES(%s,%s,%s,%s,%s) ON CONFLICT(character_id) DO UPDATE SET "
        "initial_hp=excluded.initial_hp,started_at=excluded.started_at,coefficient=excluded.coefficient,last_at=excluded.last_at",
        (character["id"], hp, now, coefficient, now),
    )
    db.execute(
        "INSERT INTO fight_health_exits(generation,fight_id,character_id,reason,created_at) VALUES(%s,%s,%s,%s,%s)",
        (generation, fight.id, character["id"], reason, now),
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
    from .fight_store import abort

    try:
        with store.connection() as db:
            result = persist(
                store,
                account_id,
                generation,
                character,
                fight,
                reason="abort",
                db=db,
            )
            abort(store, account_id, character["id"], fight.id, db=db)
        return result
    except ValueError:
        # A replaced session cannot update health. Its old durable identity
        # can still be released without touching the current character/fight.
        abort(store, account_id, character["id"], fight.id)
        return None
