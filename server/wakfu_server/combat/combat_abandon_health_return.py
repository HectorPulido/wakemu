"""Complete exploration health only after an authenticated abandonment ACK."""
from .combat_terminal_metadata import registered_summon_actor_ids
from wakfu_server import health, health_policy


def complete(store, db, account_id, generation, character, fight):
    """Preserve abort provenance and acknowledge each owned PC exactly once."""
    from psycopg.pq import TransactionStatus

    if db.info.transaction_status != TransactionStatus.INTRANS:
        raise ValueError("Abandon health return requires an active transaction")
    row = db.execute(
        "SELECT status FROM combat_fights WHERE id=%s FOR UPDATE", (fight.id,)
    ).fetchone()
    if row is None or row["status"] != "aborted" or fight.phase != "finished":
        raise ValueError("Abandon health return requires a committed terminal abort")
    main_id = character["id"]
    store.lock_character(db, account_id, generation, main_id)
    summons = registered_summon_actor_ids(fight)
    identities = {
        actor.id
        for actor in fight.actors.values()
        if actor.controlled and actor.owner_id == account_id and actor.id not in summons
    }
    members = tuple(
        db.execute(
            "SELECT character_id,session_generation FROM combat_fight_participants "
            "WHERE fight_id=%s AND account_id=%s ORDER BY character_id FOR UPDATE",
            (fight.id, account_id),
        )
    )
    if (
        main_id not in identities
        or identities != {member["character_id"] for member in members}
        or any(member["session_generation"] != generation for member in members)
    ):
        raise ValueError("Abandon health return lacks its complete owned roster")
    characters = {}
    applied = False
    for member in members:
        identity = member["character_id"]
        store.lock_character(
            db, account_id, generation, identity, selected=identity == main_id
        )
        saved = store.character(account_id, identity, db)
        receipt = db.execute(
            "SELECT reason,generation,created_at,abandon_return_acknowledged_at "
            "FROM fight_health_exits WHERE fight_id=%s AND character_id=%s FOR UPDATE",
            (fight.id, identity),
        ).fetchone()
        if (
            receipt is None
            or receipt["reason"] != "abort"
            or receipt["generation"] != generation
        ):
            raise ValueError("Abandon health return lacks its original abort receipt")
        if receipt["abandon_return_acknowledged_at"] is None:
            newer = db.execute(
                "SELECT 1 FROM fight_health_exits WHERE character_id=%s "
                "AND fight_id<>%s AND created_at>=%s LIMIT 1",
                (identity, fight.id, receipt["created_at"]),
            ).fetchone()
            active = db.execute(
                "SELECT 1 FROM combat_fight_participants p JOIN combat_fights f "
                "ON f.id=p.fight_id WHERE p.character_id=%s AND p.fight_id<>%s "
                "AND f.status IN ('placement','active') "
                "AND NOT EXISTS(SELECT 1 FROM combat_pve_withdrawals w "
                "WHERE w.fight_id=p.fight_id AND w.character_id=p.character_id) LIMIT 1",
                (identity, fight.id),
            ).fetchone()
            if newer is not None or active is not None:
                raise ValueError(
                    "Abandon health return was superseded by another fight"
                )
            if saved["health_dead"]:
                baseline = db.execute(
                    "SELECT initial_hp,initial_damage,started_at,coefficient "
                    "FROM character_regeneration WHERE character_id=%s FOR UPDATE",
                    (identity,),
                ).fetchone()
                if (
                    saved["hp"] != 0
                    or baseline is None
                    or baseline["initial_hp"] != 0
                    or baseline["initial_damage"] != saved["hp_damage"]
                    or baseline["coefficient"] != 0
                    or baseline["started_at"] != receipt["created_at"]
                ):
                    raise ValueError(
                        "Dead abandon health no longer matches its exit baseline"
                    )
                damage, dead = health_policy.recover_finished_return(
                    saved["max_hp"], saved["hp_damage"], True
                )
                hp = health_policy.apply_damage(db, saved, damage, dead)
                now = store.now()
                db.execute(
                    "INSERT INTO character_regeneration(character_id,initial_hp,started_at,coefficient,last_at) "
                    "VALUES(%s,%s,%s,%s,%s) ON CONFLICT(character_id) DO UPDATE SET "
                    "initial_hp=excluded.initial_hp,started_at=excluded.started_at,"
                    "coefficient=excluded.coefficient,last_at=excluded.last_at",
                    (
                        identity,
                        hp,
                        now,
                        health.exploration_coefficient(saved["max_hp"], hp),
                        now,
                    ),
                )
            db.execute(
                "UPDATE fight_health_exits SET abandon_return_acknowledged_at=%s "
                "WHERE fight_id=%s AND character_id=%s AND abandon_return_acknowledged_at IS NULL",
                (store.now(), fight.id, identity),
            )
            applied = True
        characters[identity] = store.character(account_id, identity, db)
    return dict(character=characters[main_id], characters=characters, applied=applied)
