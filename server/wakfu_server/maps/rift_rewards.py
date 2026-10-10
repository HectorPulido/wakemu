"""Configurable local DEV rift loot through existing atomic combat delivery.

Native references are real physical items, not virtual socket effect IDs.
Every chance, selection and quantity draw is recorded with its frozen policy.
No appearance is learned automatically; recipients use the awarded item.
"""
from decimal import Decimal
from hashlib import sha256
import json
import secrets

from psycopg.types.json import Jsonb
from psycopg.pq import TransactionStatus

ALGORITHM = "local-dev-rift-items-v1"


def _int(value, name, low, high):
    if type(value) is not int or not low <= value <= high:
        raise ValueError("Invalid rift reward " + name)
    return value


def validate_policy(policy):
    if not isinstance(policy, dict) or policy.get("kind") != "local_dev_items_v1":
        raise ValueError("Explicit local DEV rift item policy required")
    if set(policy) != {
        "kind",
        "version",
        "minimum_completed_waves",
        "minimum_defeated_monsters",
        "losses",
        "max_rolls_per_pool",
        "pools",
    }:
        raise ValueError("Unknown or missing rift reward policy fields")
    _int(policy["version"], "version", 1, 2147483647)
    _int(policy["minimum_completed_waves"], "minimum waves", 1, 10000)
    _int(policy["minimum_defeated_monsters"], "minimum kills", 1, 100000)
    _int(policy["max_rolls_per_pool"], "roll limit", 1, 128)
    if (
        policy["losses"] != "none"
        or not isinstance(policy["pools"], list)
        or not 1 <= len(policy["pools"]) <= 16
    ):
        raise ValueError("Unsupported rift losses or reward pools")
    names = set()
    for pool in policy["pools"]:
        if not isinstance(pool, dict) or set(pool) != {
            "name",
            "category",
            "references",
            "every_waves",
            "chance_bp",
            "quantity_min",
            "quantity_max",
        }:
            raise ValueError("Malformed rift reward pool")
        if (
            not isinstance(pool["name"], str)
            or not pool["name"]
            or pool["name"] in names
        ):
            raise ValueError("Invalid rift reward pool name")
        names.add(pool["name"])
        if pool["category"] not in ("item", "appearance", "enchantment"):
            raise ValueError("Invalid rift reward category")
        refs = pool["references"]
        if not isinstance(refs, list) or not refs or len(refs) > 1024:
            raise ValueError("Invalid rift reward allowlist")
        for ref in refs:
            _int(ref, "reference", 1, 2147483647)
        if len(set(refs)) != len(refs):
            raise ValueError("Duplicate rift reward allowlist reference")
        _int(pool["every_waves"], "wave interval", 1, 10000)
        _int(pool["chance_bp"], "chance", 0, 10000)
        _int(pool["quantity_min"], "minimum quantity", 1, 32767)
        _int(pool["quantity_max"], "maximum quantity", pool["quantity_min"], 32767)
        if pool["category"] == "appearance" and pool["quantity_max"] != 1:
            raise ValueError("Learnable appearances require one physical item")
    return policy


def plan(policy, result, *, rng=secrets.randbelow):
    """Pure per-character draws; only actual durable cleared waves qualify."""
    validate_policy(policy)
    waves = _int(result["completed_waves"], "completed waves", 0, 10000)
    kills = _int(result["defeated_monsters"], "defeated monsters", 0, 100000)
    if (
        result["outcome"] != "won"
        or waves < policy["minimum_completed_waves"]
        or kills < policy["minimum_defeated_monsters"]
    ):
        return []
    draws = []

    def draw(limit):
        return _int(rng(limit), "random draw", 0, limit - 1)

    for index, pool in enumerate(policy["pools"]):
        for attempt in range(
            min(policy["max_rolls_per_pool"], waves // pool["every_waves"])
        ):
            chance = draw(10000)
            chosen = draw(len(pool["references"]))
            quantity = draw(pool["quantity_max"] - pool["quantity_min"] + 1)
            draws.append(
                dict(
                    pool_index=index,
                    attempt=attempt,
                    chance_draw=chance,
                    selection_draw=chosen,
                    quantity_draw=quantity,
                    reference=pool["references"][chosen],
                    success=chance < pool["chance_bp"],
                    quantity=pool["quantity_min"] + quantity,
                )
            )
    return draws


def _validate_native(db, policy):
    from wakfu_server.inventory_move import STACKS
    from wakfu_server.combat_drop_delivery import _template_binding
    from wakfu_server.socket_enchantment import (
        SHARD_MATERIAL_REFERENCE,
        _bonus_catalog,
        _native_sublimation_pattern,
    )

    for pool in policy["pools"]:
        for ref in pool["references"]:
            if ref in _bonus_catalog():
                raise ValueError("Virtual socket bonus is not a physical reward item")
            if ref not in STACKS:
                raise ValueError("Rift reward has no supported native stack template")
            enum, _, _ = _template_binding(ref)
            if enum not in (
                "NOT_BOUND",
                "BOUND_ON_PICKUP_TO_ACCOUNT",
                "BOUND_ON_PICKUP_TO_CHARACTER",
            ):
                raise ValueError("Unsupported rift reward binding")
            if db.execute(
                "SELECT 1 FROM mount_models WHERE reference=%s", (ref,)
            ).fetchone():
                raise ValueError("Rift reward mounts require separate native authority")
            cosmetic = db.execute(
                "SELECT has_criteria FROM native_cosmetic_learning_actions WHERE item_ref=%s",
                (ref,),
            ).fetchone()
            if pool["category"] == "appearance" and (
                cosmetic is None or cosmetic["has_criteria"]
            ):
                raise ValueError(
                    "Rift appearance is not a verified learnable native item"
                )
            if cosmetic is not None and pool["category"] != "appearance":
                raise ValueError("Learnable item requires appearance reward category")
            if (
                pool["category"] == "enchantment"
                and ref != SHARD_MATERIAL_REFERENCE
                and _native_sublimation_pattern(db, ref) is None
            ):
                raise ValueError("Unverified physical enchantment material")


def apply(db, run, result, *, store, eligible_character_ids, rng=secrets.randbelow):
    """Award a frozen winning subset in the caller's settlement transaction."""
    if db.info.transaction_status != TransactionStatus.INTRANS:
        raise ValueError("Rift reward delivery requires an active transaction")
    from wakfu_server import combat_drops, combat_drop_delivery

    # Lock the same durable run as settle; callers cannot substitute counters.
    from wakfu_server.rift_runtime import _run

    canonical = _run(db, run["instance_id"])
    if (
        canonical["fight_id"] != run["fight_id"]
        or canonical["members"] != run["members"]
    ):
        raise ValueError("Rift reward run identity changed")
    if (
        canonical["status"] != "running"
        or result["outcome"] == "won"
        and result["turn"] < canonical["policy"]["turn_budget"]
    ):
        raise ValueError("Rift reward survival is not durably eligible")
    if (
        result["completed_waves"] != canonical["completed_waves"]
        or result["defeated_monsters"] != canonical["defeated_monsters"]
    ):
        raise ValueError("Rift rewards require durable actual progress")
    ids = tuple(eligible_character_ids)
    if len(set(ids)) != len(ids) or any(
        type(cid) is not int or cid not in canonical["members"] for cid in ids
    ):
        raise ValueError("Rift reward recipient is outside frozen membership")
    configured = db.execute(
        "SELECT value FROM settings WHERE name='rift_reward_policy'"
    ).fetchone()
    if configured is None:
        raise ValueError("Missing rift reward policy")
    policy = validate_policy(configured["value"])
    _validate_native(db, policy)
    if result["outcome"] != "won":
        return ()
    roster = db.execute(
        "SELECT actor_ids,species_refs FROM rift_wave_rosters WHERE instance_id=%s ORDER BY wave LIMIT 1",
        (run["instance_id"],),
    ).fetchone()
    if roster is None:
        raise ValueError("Rift rewards lack an authoritative native enemy roster")
    actor_id, species_ref = roster["actor_ids"][0], roster["species_refs"][0]
    awarded = []
    for cid in sorted(ids):
        old = db.execute(
            "SELECT * FROM rift_item_reward_receipts WHERE instance_id=%s AND character_id=%s",
            (run["instance_id"], cid),
        ).fetchone()
        if old is not None:
            awarded.append(cid)
            continue
        member = db.execute(
            "SELECT p.account_id,p.session_generation,p.team,f.status FROM combat_fight_participants p JOIN combat_fights f ON f.id=p.fight_id WHERE p.fight_id=%s AND p.character_id=%s FOR UPDATE OF f",
            (run["fight_id"], cid),
        ).fetchone()
        if (
            member is None
            or member["team"] != 0
            or member["status"] != "finished"
            or not member["session_generation"]
        ):
            raise ValueError("Rift rewards require finished durable participant lease")
        store.lock_character(
            db, member["account_id"], member["session_generation"], cid
        )
        draws = plan(policy, result, rng=rng)
        snapshot = dict(
            algorithm=ALGORITHM,
            account_id=member["account_id"],
            generation=member["session_generation"],
            instance_id=run["instance_id"],
            policy=policy,
            result=result,
            eligible_character_ids=sorted(ids),
            draws=draws,
        )
        encoded = combat_drops._canonical_json(snapshot)
        digest = sha256(encoded.encode("utf8")).hexdigest()
        version = db.execute(
            "SELECT version FROM combat_drop_policy_active WHERE singleton=true"
        ).fetchone()["version"]
        db.execute(
            "INSERT INTO fight_drop_awards(fight_id,character_id,account_id,generation,policy_version,snapshot,snapshot_sha256) VALUES(%s,%s,%s,%s,%s,%s,%s)",
            (
                run["fight_id"],
                cid,
                member["account_id"],
                member["session_generation"],
                version,
                Jsonb(snapshot),
                digest,
            ),
        )
        for draw in draws:
            pool = policy["pools"][draw["pool_index"]]
            probability = Decimal(pool["chance_bp"]) / 10000
            db.execute(
                "INSERT INTO fight_drop_attempt_receipts(fight_id,character_id,defeated_actor_id,monster_reference,drop_row_index,attempt_index,item_reference,success,quantity,quantity_min,quantity_max,base_probability,raw_probability,effective_probability,draw_numerator,quantity_draw_numerator,roll_count,native_roll_max,native_min_prospection) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,1,1,0)",
                (
                    run["fight_id"],
                    cid,
                    actor_id,
                    species_ref,
                    draw["pool_index"],
                    draw["attempt"],
                    draw["reference"],
                    draw["success"],
                    draw["quantity"] if draw["success"] else None,
                    pool["quantity_min"],
                    pool["quantity_max"],
                    probability,
                    probability,
                    probability,
                    draw["chance_draw"],
                    draw["quantity_draw"] if draw["success"] else None,
                ),
            )
        batch = combat_drops._stored_batch(db, run["fight_id"], cid)
        combat_drop_delivery.apply(store, db, batch)
        db.execute(
            "INSERT INTO rift_item_reward_receipts(instance_id,character_id,fight_id,policy_snapshot,eligibility_snapshot) VALUES(%s,%s,%s,%s,%s)",
            (
                run["instance_id"],
                cid,
                run["fight_id"],
                Jsonb(policy),
                Jsonb(dict(result=result, eligible_character_ids=sorted(ids))),
            ),
        )
        awarded.append(cid)
    return tuple(awarded)


def delivery(db, store, instance_id, character_id):
    """Read native client delivery only after durable item award; never reroll."""
    from wakfu_server import combat_drops, combat_drop_delivery
    from wakfu_server.inventory_move import synchronization
    from wakfu_server.inventory_items import equipment_inventory

    row = db.execute(
        "SELECT r.fight_id,c.account_id FROM rift_item_reward_receipts r JOIN characters c ON c.id=r.character_id WHERE r.instance_id=%s AND r.character_id=%s",
        (instance_id, character_id),
    ).fetchone()
    if row is None:
        return dict(loots=[], packets=[])
    batch = combat_drops._stored_batch(db, row["fight_id"], character_id)
    saved = store.character(row["account_id"], character_id, db)
    return dict(
        loots=combat_drops.report_loots(batch),
        packets=[
            synchronization(saved),
            equipment_inventory(saved),
            combat_drop_delivery.temporary_update(db, character_id),
        ],
    )
