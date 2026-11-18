"""Audited recovery of omitted, never-rolled native quest loot decisions.

An exact reviewed empty award is required. Existing random outcomes and the
immutable allocation receipt are never replaced. The normal native planner,
allocation filter and delivery adapter perform all decisions and item writes.
"""

from hashlib import sha256
from psycopg.types.json import Jsonb


def reconcile(store, db, fight_id, character_id, *, reviewed_snapshot_sha256):
    from wakfu_server import combat_drops, combat_drop_delivery, drop_allocation
    from wakfu_server import native_quest_complex_loot as policy
    from wakfu_server.achievements import storage, owned_quest_terminal_recovery
    from wakfu_server.combat_reward_ownership import _durable_settlement_scope

    if (
        not isinstance(reviewed_snapshot_sha256, str)
        or len(reviewed_snapshot_sha256) != 64
    ):
        raise ValueError("Missing reviewed original quest loot digest")
    key = f"native-quest-loot-reconciliation:{fight_id}:{reviewed_snapshot_sha256}"
    old = db.execute(
        "SELECT payload FROM character_achievement_events WHERE character_id=%s AND event_key=%s",
        (character_id, key),
    ).fetchone()
    batch = combat_drops._stored_batch(db, fight_id, character_id)
    if old is not None:
        if (
            batch is None
            or batch.snapshot_sha256 != old["payload"]["new_snapshot_sha256"]
        ):
            raise ValueError("Quest loot reconciliation receipt conflicts")
        return dict(old["payload"], replay=True)
    if (
        batch is None
        or batch.snapshot_sha256 != reviewed_snapshot_sha256
        or batch.decisions
        or batch.snapshot.get("attempt_count") != 0
        or batch.snapshot.get("success_count") != 0
        or batch.snapshot.get("can_loot") is not True
        or batch.snapshot.get("companion_rolls")
        or batch.snapshot.get("rift_common_quantity")
        or "quest_complex_loot" in batch.snapshot.get("fight_context", {})
    ):
        raise ValueError("Recovery requires the exact unrolled empty ordinary award")
    if (
        db.execute(
            "SELECT 1 FROM fight_drop_delivery_receipts WHERE fight_id=%s AND character_id=%s",
            (fight_id, character_id),
        ).fetchone()
        is not None
    ):
        raise ValueError("Already delivered loot cannot be reconciled as empty")
    proof = db.execute(
        "SELECT f.status,c.snapshot,e.instance_id,e.room_order,e.player_team,e.status AS encounter_status "
        "FROM combat_fights f JOIN fight_checkpoints c ON c.fight_id=f.id "
        "JOIN dungeon_room_encounters e ON e.fight_id=f.id WHERE f.id=%s FOR UPDATE OF f,c,e",
        (fight_id,),
    ).fetchone()
    if (
        proof is None
        or proof["status"] != "finished"
        or proof["encounter_status"] != "victory"
    ):
        raise ValueError("Quest loot recovery requires its genuinely settled victory")
    if (
        db.execute(
            "SELECT 1 FROM dungeon_room_encounters WHERE instance_id=%s AND fight_id>%s",
            (proof["instance_id"], fight_id),
        ).fetchone()
        is not None
    ):
        raise ValueError("A later encounter supersedes this quest loot review")
    members = db.execute(
        "SELECT p.*,false AS withdrawn FROM combat_fight_participants p WHERE fight_id=%s FOR UPDATE",
        (fight_id,),
    ).fetchall()
    if (
        len(members) != 1
        or members[0]["character_id"] != character_id
        or members[0]["account_id"] != batch.snapshot["account_id"]
    ):
        raise ValueError("Quest loot recovery lost its original single owner")
    group = db.execute(
        "SELECT g.members FROM dungeon_room_spawn_receipts r JOIN combat_groups g "
        "ON g.map_id=r.asset_map_id AND g.instance_id=r.instance_id AND g.group_id=r.group_id "
        "WHERE r.instance_id=%s AND r.room_order=%s FOR UPDATE OF g",
        (proof["instance_id"], proof["room_order"]),
    ).fetchone()
    if group is None:
        raise ValueError("Quest loot recovery has no actual original spawn")
    fight = owned_quest_terminal_recovery.projection(
        proof["snapshot"],
        fight_id=fight_id,
        owner=members[0],
        monsters=group["members"],
        player_team=proof["player_team"],
    )
    permission = policy.permission(
        db, fight_id, character_id, fight=fight, original_monsters=group["members"]
    )
    if permission is None:
        raise ValueError("No reviewed native quest loot is earned by this encounter")
    context = dict(batch.snapshot["fight_context"], quest_complex_loot=permission)
    policy.validate_durable(db, fight_id, character_id, permission)
    catalog = combat_drops.native_drop_catalog()
    if catalog["source_sha256"] != batch.snapshot["source_catalog_sha256"]:
        raise ValueError("Native loot catalog changed since this reviewed award")
    frozen = batch.snapshot["modifiers"]
    decisions = combat_drops.plan_player_drops(
        monsters=batch.snapshot["monsters"],
        character_id=character_id,
        prospecting_bonus=batch.snapshot["prospection_bonus"],
        can_loot=True,
        fight_context=context,
        challenge_drop_percent=frozen["challenge_drop_percent"],
        star_bonus_percent=frozen["star_bonus_percent"],
        conquest_rate_bp=frozen["conquest_rate_bp"],
        drop_rate_bp=frozen["drop_rate_bp"],
        breach_bonus_bp=frozen["breach_bonus_bp"],
        shop_consumable_factor=batch.snapshot["shop_consumable_drop_factor"],
        catalog=catalog,
    )
    if not decisions or any(
        not policy.row_allowed(
            catalog["monsters"][d.monster_reference][d.drop_row_index],
            d.monster_reference,
            permission,
        )
        for d in decisions
    ):
        raise ValueError("Reconciliation would reroll an unrelated native loot row")
    allocation = db.execute(
        "SELECT snapshot,snapshot_sha256 FROM fight_drop_allocations WHERE fight_id=%s AND character_id=%s",
        (fight_id, character_id),
    ).fetchone()
    if (
        allocation is None
        or allocation["snapshot"].get("decisions") != []
        or allocation["snapshot"].get("accepted_counts") != {}
        or sha256(
            combat_drops._canonical_json(allocation["snapshot"]).encode()
        ).hexdigest()
        != allocation["snapshot_sha256"]
    ):
        raise ValueError("Quest loot recovery lacks its exact empty allocation")
    refs = sorted({d.item_reference for d in decisions})
    rarities = db.execute(
        "SELECT reference,rarity_code,source_sha256 FROM native_drop_item_rarities WHERE reference=ANY(%s)",
        (refs,),
    ).fetchall()
    if {r["reference"] for r in rarities} != set(refs):
        raise ValueError("Quest loot supplement lacks native rarity authority")
    filtered, audit, after = drop_allocation.filter_decisions(
        decisions,
        policy=allocation["snapshot"]["policy"],
        rarities={r["reference"]: r["rarity_code"] for r in rarities},
        consumed={},
    )
    snapshot = dict(
        batch.snapshot,
        fight_context=context,
        attempt_count=len(filtered),
        success_count=sum(d.success for d in filtered),
    )
    snapshot["native_quest_loot_reconciliation"] = dict(
        original_snapshot_sha256=reviewed_snapshot_sha256,
        original_allocation_sha256=allocation["snapshot_sha256"],
        original_snapshot=batch.snapshot,
        allocation_audit=audit,
        accepted_counts=after,
        native_rarity_sources=rarities,
    )
    new_sha = sha256(combat_drops._canonical_json(snapshot).encode()).hexdigest()
    with _durable_settlement_scope(db, fight, members):
        combat_drops.persist_decisions(db, fight_id, character_id, filtered)
        db.execute(
            "UPDATE fight_drop_awards SET snapshot=%s,snapshot_sha256=%s WHERE fight_id=%s AND character_id=%s AND snapshot_sha256=%s",
            (
                Jsonb(snapshot),
                new_sha,
                fight_id,
                character_id,
                reviewed_snapshot_sha256,
            ),
        )
        updated = combat_drops._stored_batch(db, fight_id, character_id)
        deliveries = combat_drop_delivery.apply(store, db, updated)
    receipt = dict(
        fight_id=fight_id,
        character_id=character_id,
        original_snapshot_sha256=reviewed_snapshot_sha256,
        new_snapshot_sha256=new_sha,
        original_allocation_sha256=allocation["snapshot_sha256"],
        deliveries=deliveries,
    )
    if not storage.record_event(db, character_id, key, receipt):
        raise ValueError("Quest loot reconciliation raced")
    return dict(receipt, replay=False)
