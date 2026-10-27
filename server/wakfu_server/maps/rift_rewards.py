"""Configurable local DEV rift loot through existing atomic combat delivery.

Native references are real physical items, not virtual socket effect IDs.
Every chance, selection and quantity draw is recorded with its frozen policy.
No appearance is learned automatically; recipients use the awarded item.
"""
from decimal import Decimal
from hashlib import sha256
import json
import secrets
from copy import deepcopy

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
        policy["losses"] not in ("none", "earned_native_kills")
        or not isinstance(policy["pools"], list)
        or not 1 <= len(policy["pools"]) <= 16
    ):
        raise ValueError("Unsupported rift losses or reward pools")
    names = set()
    for pool in policy["pools"]:
        if not isinstance(pool, dict) or set(pool) - {"source"} != {
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
        source = pool.get("source", "allowlist")
        if source not in ("allowlist", "native_rift_monsters"):
            raise ValueError("Invalid rift reward source")
        if source == "native_rift_monsters" and pool["category"] != "item":
            raise ValueError("Native monster source requires ordinary item category")
        refs = pool["references"]
        if (
            not isinstance(refs, list)
            or len(refs) > 32768
            or source == "allowlist"
            and not refs
        ):
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


def configured_policy(db, run):
    """Keep classic balance unchanged; select an explicit ultimate-only override."""
    configured = db.execute(
        "SELECT value FROM settings WHERE name='rift_reward_policy'"
    ).fetchone()
    if configured is None:
        raise ValueError("Missing rift reward policy")
    selected = configured["value"]
    if run["catalog"]["type"] == "ULTIMATE_INFINITE_WAVE":
        overrides = db.execute(
            "SELECT value FROM settings WHERE name='rift_reward_type_overrides'"
        ).fetchone()
        if overrides is not None:
            values = overrides["value"]
            if not isinstance(values, dict) or set(values) - {"ULTIMATE_INFINITE_WAVE"}:
                raise ValueError("Invalid scoped rift reward policy")
            selected = values.get("ULTIMATE_INFINITE_WAVE", selected)
    return validate_policy(selected)


def plan(policy, result, *, rng=secrets.randbelow):
    """Pure per-character draws; only actual durable cleared waves qualify."""
    validate_policy(policy)
    waves = _int(result["completed_waves"], "completed waves", 0, 10000)
    kills = _int(result["defeated_monsters"], "defeated monsters", 0, 100000)
    if (
        (
            result["outcome"] != "won"
            and not (
                result["outcome"] == "lost"
                and policy["losses"] == "earned_native_kills"
            )
        )
        or waves < policy["minimum_completed_waves"]
        or kills < policy["minimum_defeated_monsters"]
    ):
        return []
    draws = []

    def draw(limit):
        return _int(rng(limit), "random draw", 0, limit - 1)

    for index, pool in enumerate(policy["pools"]):
        if not pool["references"]:
            raise ValueError("Rift native reward pool must be resolved before drawing")
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


def resolve_native_pools(db, policy, species_refs, *, catalog=None):
    """Freeze physically deliverable native monster loot into local item pools.

    Native identities and criteria are authoritative; pool frequency/chance remain
    the configured local balance. No monster drop probability is reinterpreted as
    a rift probability. Complex criteria, external tables, prospecting-gated items
    and context-dependent rows without proven authority are excluded.
    """
    from wakfu_server import combat_drops
    from wakfu_server.inventory_move import STACKS
    from wakfu_server.combat_drop_delivery import _template_binding

    validate_policy(policy)
    frozen = deepcopy(policy)
    native = [p for p in frozen["pools"] if p.get("source") == "native_rift_monsters"]
    if not native:
        return frozen
    if (
        not isinstance(species_refs, (tuple, list))
        or not species_refs
        or any(type(ref) is not int or ref <= 0 for ref in species_refs)
    ):
        raise ValueError("Native reward pool requires verified rift species")
    catalog = combat_drops.native_drop_catalog() if catalog is None else catalog
    candidates = set()
    for species in species_refs:
        rows = catalog["monsters"].get(species)
        if rows is None:
            raise ValueError("Rift species has no native loot catalog")
        for row in rows:
            if (
                combat_drops._row_is_eligible(
                    row,
                    fight_context=dict(in_dungeon=False, in_infinite_waves=True),
                    effective_prospection=0,
                )
                and combat_drops._decimal(
                    row.get("probability"),
                    "native drop probability",
                    Decimal(0),
                    Decimal(1),
                )
                > 0
            ):
                ref = row.get("reference_id")
                if type(ref) is int and ref in STACKS:
                    candidates.add(ref)
    # Ordinary pools cannot bypass cosmetic learning or mount authority.
    excluded = {
        r["reference"]
        for r in db.execute(
            "SELECT reference FROM mount_models WHERE reference=ANY(%s)",
            (sorted(candidates),),
        ).fetchall()
    }
    excluded.update(
        r["item_ref"]
        for r in db.execute(
            "SELECT item_ref FROM native_cosmetic_learning_actions WHERE item_ref=ANY(%s)",
            (sorted(candidates),),
        ).fetchall()
    )
    references = []
    for ref in sorted(candidates - excluded):
        try:
            enum, _, _ = _template_binding(ref)
        except ValueError:
            continue
        if enum in (
            "NOT_BOUND",
            "BOUND_ON_PICKUP_TO_ACCOUNT",
            "BOUND_ON_PICKUP_TO_CHARACTER",
        ):
            references.append(ref)
    if not references:
        raise ValueError("Rift native reward pool has no supported eligible items")
    for pool in native:
        pool["references"] = list(references)
    validate_policy(frozen)
    return frozen


def _validate_native(db, policy):
    from wakfu_server.inventory_move import STACKS
    from wakfu_server.combat_drop_delivery import _template_binding
    from wakfu_server.socket_enchantment import (
        SHARD_MATERIAL_REFERENCE,
        _bonus_catalog,
    )
    from wakfu_server.items.sublimation_eligibility import pattern

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
            if pool["category"] == "enchantment" and ref != SHARD_MATERIAL_REFERENCE:
                try:
                    attachment = pattern(db, ref)
                except ValueError as error:
                    raise ValueError(
                        "Unverified physical enchantment material"
                    ) from error
                if attachment["kind"] != "BASIC":
                    raise ValueError("Unverified physical enchantment material")


def apply(
    db, run, result, *, store, eligible_character_ids, rng=secrets.randbelow, fight=None
):
    """Deliver ordinary earned loot and additional pools in one settlement batch."""
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
    from wakfu_server.rift_encounter_roles import roles_for_catalog
    from wakfu_server.combat_encounter_roles import assigned_roles

    roles = roles_for_catalog(canonical["catalog"], canonical["policy"])
    if fight is not None:
        actual_roles = assigned_roles(fight)
        if fight.id != canonical["fight_id"] or (
            actual_roles.player_team,
            actual_roles.npc_team,
        ) != (roles.player_team, roles.npc_team):
            raise ValueError("Rift reward fight differs from its frozen roles")
    if (
        canonical["status"] not in ("running", result["outcome"])
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
    if result["outcome"] not in ("won", "lost"):
        return ()
    existing = db.execute(
        "SELECT character_id,fight_id FROM rift_item_reward_receipts "
        "WHERE instance_id=%s AND character_id=ANY(%s)",
        (run["instance_id"], list(ids)),
    ).fetchall()
    if any(row["fight_id"] != canonical["fight_id"] for row in existing):
        raise ValueError("Rift item receipt belongs to another bound fight")
    already_awarded = {row["character_id"] for row in existing}
    if already_awarded == set(ids):
        return tuple(sorted(ids))  # Never resolve/reroll a changed live policy.
    from wakfu_server.rift_earned_rewards import defeated_sources

    if fight is None:
        raise ValueError("Earned Rift loot requires its actual finished fight")
    killed = defeated_sources(db, fight, canonical)
    if not killed:
        return ()
    policy = resolve_native_pools(
        db, configured_policy(db, canonical), canonical["catalog"]["species_refs"]
    )
    _validate_native(db, policy)
    from wakfu_server.rift_wave_bindings import rosters as bound_rosters

    rosters = bound_rosters(db, canonical, fight=fight)
    if not rosters:
        raise ValueError("Rift rewards lack an authoritative native enemy roster")
    actor_id, species_ref = killed[0]["id"], killed[0]["ref"]
    awarded = []
    for cid in sorted(ids):
        if cid in already_awarded:
            awarded.append(cid)
            continue
        member = db.execute(
            "SELECT p.account_id,p.session_generation,p.team,f.status FROM combat_fight_participants p JOIN combat_fights f ON f.id=p.fight_id WHERE p.fight_id=%s AND p.character_id=%s FOR UPDATE OF f",
            (run["fight_id"], cid),
        ).fetchone()
        if (
            member is None
            or member["team"] != roles.player_team
            or member["status"] != "finished"
            or not member["session_generation"]
        ):
            raise ValueError("Rift rewards require finished durable participant lease")
        from wakfu_server.combat_reward_ownership import lock_recipient

        lock_recipient(
            store,
            db,
            member["account_id"],
            member["session_generation"],
            cid,
            run["fight_id"],
        )
        from wakfu_server.rift_loot_quantities import ReceiptIdentities
        from wakfu_server.combat_companions import loot_profiles

        character = store.character(member["account_id"], cid, db)
        actor = fight.actors[cid]
        common = combat_drops.resolve(
            store,
            db,
            account_id=member["account_id"],
            generation=member["session_generation"],
            character_id=cid,
            fight_id=run["fight_id"],
            monsters=[dict(actor_id=row["id"], reference=row["ref"]) for row in killed],
            prospecting_bonus=combat_drops.native_prospection_bonus(actor),
            shop_consumable_factor=combat_drops.native_shop_drop_factor(actor),
            can_loot=True,
            fight_context=dict(
                downscaled=actor.effective_level < character["level"],
                in_dungeon=False,
                in_infinite_waves=True,
            ),
            companion_rolls=loot_profiles(fight, cid),
            rng=rng,
            rift_fight=fight,
        )
        if common.replayed:
            raise ValueError(
                "Rift ordinary loot lacks its atomic additional-item receipt"
            )
        identities = ReceiptIdentities(common.decisions)
        draws = plan(policy, result, rng=rng)
        for draw in draws:
            row_index, attempt_index = identities.take(actor_id)
            draw["receipt_identity"] = dict(
                drop_row_index=row_index, attempt_index=attempt_index
            )
        additional = dict(
            algorithm=ALGORITHM,
            account_id=member["account_id"],
            generation=member["session_generation"],
            instance_id=run["instance_id"],
            policy=policy,
            result=result,
            eligible_character_ids=sorted(ids),
            draws=draws,
        )
        snapshot = dict(common.snapshot, rift_additional_items=additional)
        encoded = combat_drops._canonical_json(snapshot)
        digest = sha256(encoded.encode("utf8")).hexdigest()
        db.execute(
            "UPDATE fight_drop_awards SET snapshot=%s,snapshot_sha256=%s "
            "WHERE fight_id=%s AND character_id=%s",
            (
                Jsonb(snapshot),
                digest,
                run["fight_id"],
                cid,
            ),
        )
        for draw in draws:
            pool = policy["pools"][draw["pool_index"]]
            probability = Decimal(pool["chance_bp"]) / 10000
            row_index = draw["receipt_identity"]["drop_row_index"]
            attempt_index = draw["receipt_identity"]["attempt_index"]
            db.execute(
                "INSERT INTO fight_drop_attempt_receipts(fight_id,character_id,defeated_actor_id,monster_reference,drop_row_index,attempt_index,item_reference,success,quantity,quantity_min,quantity_max,base_probability,raw_probability,effective_probability,draw_numerator,quantity_draw_numerator,roll_count,native_roll_max,native_min_prospection) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,1,1,0)",
                (
                    run["fight_id"],
                    cid,
                    actor_id,
                    species_ref,
                    row_index,
                    attempt_index,
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
