"""Reconcile legacy terminal casualties only after a proven owned return ACK."""
from psycopg.types.json import Jsonb
from . import health_policy

AUDIT_ACTION = "health.historical.acknowledged.return"


def capture(db, character):
    identity, account = character["id"], character["account_id"]
    participant = db.execute(
        "SELECT p.*,f.status,f.fight_kind FROM combat_fight_participants p "
        "JOIN combat_fights f ON f.id=p.fight_id "
        "WHERE p.character_id=%s AND p.account_id=%s AND p.entry_hp>0 "
        "ORDER BY p.fight_id DESC LIMIT 1",
        (identity, account),
    ).fetchone()
    if participant is None:
        return None
    fight_id = participant["fight_id"]
    exit_row = db.execute(
        "SELECT * FROM fight_health_exits WHERE character_id=%s "
        "ORDER BY fight_id DESC LIMIT 1",
        (identity,),
    ).fetchone()
    checkpoint = db.execute(
        "SELECT fight_id,status,snapshot->>'phase' AS phase,"
        "snapshot->'actors'->%s AS actor FROM fight_checkpoints WHERE fight_id=%s",
        (str(identity), fight_id),
    ).fetchone()
    regeneration = db.execute(
        "SELECT * FROM character_regeneration WHERE character_id=%s",
        (identity,),
    ).fetchone()
    tails = db.execute(
        "SELECT p.*,f.status,f.fight_kind,"
        "EXISTS(SELECT 1 FROM fight_health_exits e WHERE e.fight_id=p.fight_id "
        "AND e.character_id=p.character_id) AS health_exit,"
        "EXISTS(SELECT 1 FROM fight_rewards r WHERE r.fight_id=p.fight_id "
        "AND r.character_id=p.character_id) AS reward,"
        "EXISTS(SELECT 1 FROM fight_checkpoints c WHERE c.fight_id=p.fight_id) AS checkpoint "
        "FROM combat_fight_participants p JOIN combat_fights f ON f.id=p.fight_id "
        "WHERE p.character_id=%s AND p.account_id=%s AND p.fight_id>%s ORDER BY p.fight_id",
        (identity, account, fight_id),
    ).fetchall()
    active = db.execute(
        "SELECT 1 FROM combat_fight_participants p JOIN combat_fights f ON f.id=p.fight_id "
        "WHERE p.character_id=%s AND f.status IN ('placement','active') LIMIT 1",
        (identity,),
    ).fetchone()
    return dict(
        participant=participant,
        exit=exit_row,
        checkpoint=checkpoint,
        regeneration=regeneration,
        tails=tails,
        active=active,
    )


def eligible(character, maximum, evidence):
    """Fail closed for current injuries, unknown deaths and real newer fights."""
    if evidence is None or evidence["active"]:
        return False
    if (
        character["hp"] != 0
        or character["health_dead"] is not True
        or maximum != character["max_hp"]
    ):
        return False
    p, e, k, r = (
        evidence[key] for key in ("participant", "exit", "checkpoint", "regeneration")
    )
    if e is None or k is None or r is None:
        return False
    if (
        p["status"] != "finished"
        or p["fight_kind"] != "pve"
        or e["fight_id"] != p["fight_id"]
        or e["reason"] != "return"
        or e["return_acknowledged_at"] is None
        or e["return_acknowledged_at"] < e["created_at"]
        or e["generation"] != p["session_generation"]
        or k["status"] != "ended"
        or k["phase"] != "finished"
    ):
        return False
    a = k["actor"]
    if (
        not isinstance(a, dict)
        or a.get("id") != character["id"]
        or a.get("owner_id") != character["account_id"]
        or a.get("controlled") is not True
        or a.get("hp") != 0
        or a.get("max_hp") != maximum
        or a.get("team") != p["team"]
        or p["entry_health_dead"] is not False
        or type(p["entry_hp"]) is not int
        or p["entry_hp"] <= 0
        or p["entry_max_hp"] != maximum
        or type(p["entry_hp_damage"]) is not int
    ):
        return False
    projected = p["entry_hp_damage"] + maximum - (maximum - p["entry_hp"])
    if (
        projected != character["hp_damage"]
        or r["initial_hp"] != 0
        or r["initial_damage"] != projected
        or r["coefficient"] != 0
        or r["started_at"] < e["created_at"]
        or r["last_at"] < r["started_at"]
    ):
        return False
    for tail in evidence["tails"]:
        if (
            tail["status"] != "aborted"
            or tail["fight_kind"] != "pve"
            or tail["entry_hp"] != 0
            or tail["entry_max_hp"] != maximum
            or tail["entry_hp_damage"] != projected
            or tail["entry_health_dead"] is not True
            or tail["health_exit"]
            or tail["reward"]
            or tail["checkpoint"]
        ):
            return False
    return True


def reconcile(db, character, maximum):
    """Caller must hold the ordinary owned session and character locks.

    Selection runs this inside health initialization's transaction. Regeneration
    is subsequently initialized by that same transaction, starting now rather
    than granting healing for time spent in the historical dead state.
    """
    if character["hp"] != 0 or character["health_dead"] is not True:
        return character
    evidence = capture(db, character)
    if not eligible(character, maximum, evidence):
        return character
    fight_id = evidence["participant"]["fight_id"]
    previous = db.execute(
        "SELECT 1 FROM admin_panel_audit WHERE action=%s AND target=%s "
        "AND after_data->>'fight_id'=%s LIMIT 1",
        (AUDIT_ACTION, str(character["id"]), str(fight_id)),
    ).fetchone()
    if previous:
        return character
    damage, dead = health_policy.recover_finished_return(
        maximum, character["hp_damage"], character["health_dead"]
    )
    hp = health_policy.apply_damage(db, character, damage, dead)
    db.execute(
        "INSERT INTO admin_panel_audit(operator,action,target,before_data,after_data) "
        "VALUES(%s,%s,%s,%s,%s)",
        (
            "owned-selection-reconciliation",
            AUDIT_ACTION,
            str(character["id"]),
            Jsonb(
                dict(
                    hp=character["hp"],
                    hp_damage=character["hp_damage"],
                    health_dead=character["health_dead"],
                )
            ),
            Jsonb(
                dict(
                    fight_id=fight_id,
                    character_id=character["id"],
                    hp=hp,
                    hp_damage=damage,
                    health_dead=dead,
                    policy="acknowledged-terminal-return-v1",
                )
            ),
        ),
    )
    return dict(character, hp=hp, hp_damage=damage, health_dead=dead)
