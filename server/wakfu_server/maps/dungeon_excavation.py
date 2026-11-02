"""Transactional excavation primitives; callers own lease/location/inventory locks.

No wire handler is installed by this candidate. The public provider must acquire
run -> account/lease -> character/item ownership and preserve native admission.
"""
import hashlib
import json
import secrets
from psycopg.types.json import Jsonb
from wakfu_server import consumable_buffs, dungeon_rotation, dungeon_scenario_states


def digest(value):
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode()
    ).hexdigest()


def validate_rule(rule):
    if (
        rule.get("outcome") != "excavation_state"
        or rule.get("consume_units") != 0
        or rule.get("key_probability") != [1, 10]
        or type(rule.get("attempt_interval_ms")) is not int
        or not 1 <= rule["attempt_interval_ms"] <= 60000
        or rule.get("timing_authority")
        != "explicit_reconstruction_not_native_action_parameters"
        or not rule.get("ground_authority", {}).get("targets")
        or rule.get("ground_authority", {}).get("authority")
        != "reviewed_native_sand_reconstruction"
    ):
        raise ValueError("Unqualified reusable excavation policy")


def _fresh_run(db, instance_id):
    run = db.execute(
        "SELECT * FROM dungeon_room_runs WHERE instance_id=%s FOR UPDATE",
        (instance_id,),
    ).fetchone()
    if (
        run is None
        or run["status"] != "active"
        or run["current_room"] != 1
        or run["revision"] != 1
    ):
        raise ValueError("Excavation choice requires a new unearned dungeon run")
    for table in ("dungeon_room_spawn_receipts", "dungeon_room_encounters"):
        if (
            db.execute(
                f"SELECT 1 FROM {table} WHERE instance_id=%s LIMIT 1", (instance_id,)
            ).fetchone()
            is not None
        ):
            raise ValueError("Cannot replace earned or spawned dungeon progression")
    return run


def attempt_locked(
    store,
    db,
    *,
    instance_id,
    character,
    item,
    request,
    rule,
    now_ms=None,
    randbelow=None,
):
    """No shovel consumption; one persisted RNG result per accepted time window.

    now_ms is server-owned only. No client action nonce exists in bIg; duplicates
    inside the explicit interval replay the receipt, never reroll. A later valid
    request is a new excavation, not identifiable as a transport-level replay.
    """
    consumable_buffs._context(store, db, character["id"], now_ms)
    now_ms = int(store.clock() * 1000) if now_ms is None else now_ms
    validate_rule(rule)
    run = _fresh_run(db, instance_id)
    if (
        character.get("instance_id") != instance_id
        or item["character_id"] != character["id"]
        or item["uid"] != request["source_uid"]
        or item["quantity"] < 1
        or item["reference"] != rule["item_reference"]
        or request["action_id"] != rule["action_id"]
        or character["map_id"] != rule["ground_authority"]["map_id"]
    ):
        raise ValueError("Excavation source or location changed")
    targets = [
        t
        for t in rule["ground_authority"]["targets"]
        if t["position"][:2] == [request["x"], request["y"]]
    ]
    position = [character[k] for k in ("x", "y", "z")]
    if len(targets) != 1 or position not in targets[0]["approach_cells"]:
        raise ValueError("Excavation target lacks its native adjacent approach")
    rule_hash = digest(rule)
    db.execute(
        "INSERT INTO dungeon_excavation_runs(instance_id,catalog_hash,rule_sha256) VALUES(%s,%s,%s) ON CONFLICT(instance_id) DO NOTHING",
        (instance_id, run["catalog_hash"], rule_hash),
    )
    state = db.execute(
        "SELECT * FROM dungeon_excavation_runs WHERE instance_id=%s FOR UPDATE",
        (instance_id,),
    ).fetchone()
    if (
        state["catalog_hash"] != run["catalog_hash"]
        or state["rule_sha256"] != rule_hash
    ):
        raise ValueError("Pinned excavation authority changed")
    if state["selected_source_id"] is not None:
        raise ValueError("Initial key choice is already frozen")
    if state["key_state_uid"] is not None:
        return dict(
            consumed=0,
            found_key=True,
            replay=True,
            key_character_id=state["key_character_id"],
        )
    db.execute(
        "INSERT INTO dungeon_excavation_actors(instance_id,character_id) VALUES(%s,%s) ON CONFLICT DO NOTHING",
        (instance_id, character["id"]),
    )
    actor = db.execute(
        "SELECT * FROM dungeon_excavation_actors WHERE instance_id=%s AND character_id=%s FOR UPDATE",
        (instance_id, character["id"]),
    ).fetchone()
    if now_ms < actor["next_attempt_ms"]:
        prior = db.execute(
            "SELECT * FROM dungeon_excavation_attempts WHERE instance_id=%s AND character_id=%s AND attempt=%s",
            (instance_id, character["id"], actor["last_attempt"]),
        ).fetchone()
        if prior is None:
            raise ValueError("Excavation retry has no authoritative receipt")
        return dict(consumed=0, found_key=prior["found_key"], replay=True)
    draw = (secrets.randbelow if randbelow is None else randbelow)(10)
    if type(draw) is not int or not 0 <= draw < 10:
        raise ValueError("Invalid server excavation draw")
    found = draw == 0
    attempt = actor["last_attempt"] + 1
    db.execute(
        "INSERT INTO dungeon_excavation_attempts(instance_id,character_id,attempt,source_uid,target,found_key) VALUES(%s,%s,%s,%s,%s,%s)",
        (
            instance_id,
            character["id"],
            attempt,
            item["uid"],
            Jsonb(targets[0]["position"]),
            found,
        ),
    )
    db.execute(
        "UPDATE dungeon_excavation_actors SET last_attempt=%s,next_attempt_ms=%s WHERE instance_id=%s AND character_id=%s",
        (attempt, now_ms + rule["attempt_interval_ms"], instance_id, character["id"]),
    )
    if found:
        uid = dungeon_scenario_states.grant(
            store,
            db,
            character["id"],
            instance_id=instance_id,
            rule_sha256=rule_hash,
            source_uid=item["uid"],
            descriptor=rule["key_state"],
        )
        db.execute(
            "UPDATE dungeon_excavation_runs SET key_character_id=%s,key_state_uid=%s WHERE instance_id=%s",
            (character["id"], uid, instance_id),
        )
    return dict(
        consumed=0,
        found_key=found,
        replay=False,
        attempt=attempt,
        key_character_id=character["id"] if found else None,
    )


def choose_locked(store, db, *, instance_id, character_id, config, source_id):
    """Freeze shared-party first choice once, before any encounter receipt.

    Provider must validate actual native Door action/range and active membership.
    This function consumes only the instance-qualified native carrier UID. The
    key carrier must be the interacting member; native actor state ownership is
    preserved rather than inventing a party-wide transferable key.
    """
    consumable_buffs._context(store, db, character_id, None)
    run = db.execute(
        "SELECT * FROM dungeon_room_runs WHERE instance_id=%s FOR UPDATE",
        (instance_id,),
    ).fetchone()
    state = db.execute(
        "SELECT * FROM dungeon_excavation_runs WHERE instance_id=%s FOR UPDATE",
        (instance_id,),
    ).fetchone()
    if run is None or state is None or state["catalog_hash"] != run["catalog_hash"]:
        raise ValueError("Initial door lacks pinned excavation authority")
    if state["selected_source_id"] is not None:
        if state["selected_source_id"] != source_id or run["branch_key"] != str(
            source_id
        ):
            raise ValueError("Conflicting replay of immutable first door")
        return dict(replay=True, selected_source_id=source_id)
    _fresh_run(db, instance_id)
    if run.get("branch_key") is not None or state["key_state_uid"] is None:
        raise ValueError("Initial native door requires the unspent key")
    if state["key_character_id"] != character_id:
        raise ValueError("The native key carrier must open the initial door")
    from wakfu_server.dungeon_rotation_cache import project_pinned

    projected = project_pinned(config, source_id)
    rooms = [
        dict(
            order=r["order"],
            monsters=[
                dict(
                    ref_id=m["ref_id"],
                    count=m["count"],
                    min_level=m["native_min_level"],
                    max_level=m["native_max_level"],
                    role=m["role"],
                )
                for m in r["monsters"]
            ],
        )
        for r in projected["compiled_plan"]["rooms"]
        if r["order"] <= len(dungeon_rotation.source_order(config, source_id))
    ]
    dungeon_scenario_states.consume(
        store,
        db,
        state["key_character_id"],
        uid=state["key_state_uid"],
        instance_id=instance_id,
        rule_sha256=state["rule_sha256"],
    )
    db.execute(
        "UPDATE dungeon_room_runs SET branch_key=%s,rooms=%s WHERE instance_id=%s",
        (str(source_id), Jsonb(rooms), instance_id),
    )
    db.execute(
        "UPDATE dungeon_excavation_runs SET selected_source_id=%s,selected_rooms_sha256=%s WHERE instance_id=%s",
        (source_id, digest(rooms), instance_id),
    )
    return dict(
        replay=False,
        selected_source_id=source_id,
        state_character_id=state["key_character_id"],
        projected=projected,
    )
