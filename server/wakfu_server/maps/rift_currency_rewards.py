"""Exactly-once rift XP/kamas: fifty times the ordinary per-recipient reward.

The ordinary configured reward policy owns monster values, Wisdom, party and
level scaling, global rates, conquest rates and the single inclusive kama roll.
Physical rift item pools and their probabilities are independent of this module.
"""
from hashlib import sha256
import json
from types import SimpleNamespace

from psycopg.pq import TransactionStatus
from psycopg.types.json import Jsonb

from wakfu_server import combat_reward_context, combat_rewards, reward_policy

MULTIPLIER = 50
ALGORITHM = "rift-fifty-times-ordinary-xp-kamas-v1"


def reward_context(fight, character, run, rosters, eligible_character_ids):
    """Compare accumulated native sources with every durable admitted wave.

    Count only defeated original enemies, including kills from the unfinished
    final wave. Summons, living enemies and merely planned waves never pay.
    """
    sources = getattr(fight, "rift_monsters", None)
    if not isinstance(sources, dict):
        raise ValueError("Rift reward lacks accumulated trusted native sources")
    bound = {}
    for roster in rosters:
        ids, refs = roster["actor_ids"], roster["species_refs"]
        if not ids or len(ids) != len(refs):
            raise ValueError("Malformed durable rift reward roster")
        for identity, ref in zip(ids, refs):
            if (
                type(identity) is not int
                or identity >= 0
                or identity in bound
                or type(ref) is not int
                or ref <= 0
            ):
                raise ValueError("Invalid or duplicate durable rift enemy")
            bound[identity] = ref
    if set(sources) != set(bound):
        raise ValueError("Rift accumulated sources differ from admitted waves")
    killed = []
    for identity, reference in sorted(bound.items()):
        source, actor = sources[identity], fight.actors.get(identity)
        if (
            actor is None
            or actor.id != identity
            or actor.controlled
            or actor.team != 1
            or combat_reward_context._summon(actor)
            or source.get("id") != identity
            or source.get("ref") != reference
            or source.get("instance_id") != run["instance_id"]
            or source.get("level") != actor.effective_level
        ):
            raise ValueError(
                "Rift original enemy differs from durable/native authority"
            )
        if actor.hp <= 0:
            killed.append(source)
    eligible = tuple(eligible_character_ids)
    if len(set(eligible)) != len(eligible) or any(
        type(cid) is not int or cid not in run["members"] for cid in eligible
    ):
        raise ValueError("Rift reward eligibility differs from frozen membership")
    winners = {
        identity: actor
        for identity, actor in fight.actors.items()
        if actor.controlled
        and actor.team == 0
        and not combat_reward_context._summon(actor)
        and not getattr(actor, "pve_withdrawn", False)
    }
    if set(winners) != set(eligible) or character["id"] not in winners:
        raise ValueError("Rift reward eligibility differs from actual participants")
    if not killed:
        return None, ()
    view = SimpleNamespace(
        phase="finished",
        winner=0,
        actors={
            **winners,
            **{source["id"]: fight.actors[source["id"]] for source in killed},
        },
    )
    context = combat_reward_context.build_context(view, character, tuple(killed))
    snapshot = tuple(
        dict(actor_id=source["id"], reference=source["ref"], level=source["level"])
        for source in killed
    )
    return context, snapshot


def scaled_policy(baseline, totals):
    """Apply the multiplier after ordinary rounding, then native/storage caps."""
    return combat_rewards.Policy(
        xp=min(baseline.xp * MULTIPLIER, (2**63 - 1) - totals["xp"]),
        kamas=min(
            baseline.kamas * MULTIPLIER, 2**31 - 1, (2**63 - 1) - totals["kamas"]
        ),
    )


def resolve(
    store,
    db,
    *,
    account_id,
    generation,
    character_id,
    fight,
    character,
    eligible_character_ids
):
    """Return the frozen scaled Policy inside the ordinary award transaction."""
    if db.info.transaction_status != TransactionStatus.INTRANS:
        raise ValueError("Rift currency reward requires an active transaction")
    state = getattr(fight, "rift_wave_state", None)
    if not isinstance(state, dict):
        raise ValueError("Rift currency reward lacks its durable run identity")
    from wakfu_server.rift_runtime import _run

    run = _run(db, state["instance_id"])
    if run["fight_id"] != fight.id:
        raise ValueError("Rift currency reward belongs to another fight")
    receipt = db.execute(
        "SELECT outcome,result FROM rift_settlement_receipts WHERE instance_id=%s AND fight_id=%s",
        (run["instance_id"], fight.id),
    ).fetchone()
    if receipt is None:
        raise ValueError("Rift currency reward requires durable terminal settlement")
    actor = fight.actors.get(character_id)
    if (
        receipt["outcome"] != "won"
        or fight.winner != 0
        or actor is None
        or getattr(actor, "pve_withdrawn", False)
    ):
        return combat_rewards.Policy()
    if (
        fight.phase != "finished"
        or run["status"] != "won"
        or receipt["result"]["turn"] < run["policy"]["turn_budget"]
        or character["id"] != character_id
        or character["account_id"] != account_id
    ):
        raise ValueError("Rift currency reward survival or recipient is invalid")
    from wakfu_server.combat_reward_ownership import lock_recipient

    lock_recipient(store, db, account_id, generation, character_id, fight.id)
    old = db.execute(
        "SELECT * FROM fight_reward_policy_receipts WHERE fight_id=%s AND character_id=%s FOR UPDATE",
        (fight.id, character_id),
    ).fetchone()
    if old is not None:
        if old["account_id"] != account_id:
            raise ValueError("Rift currency receipt belongs to another account")
        return reward_policy._existing_decision(old).policy
    rosters = db.execute(
        "SELECT actor_ids,species_refs FROM rift_wave_rosters WHERE instance_id=%s ORDER BY wave",
        (run["instance_id"],),
    ).fetchall()
    context, killed = reward_context(
        fight, character, run, rosters, eligible_character_ids
    )
    if context is None:
        return combat_rewards.Policy()
    ordinary = reward_policy.resolve(
        store,
        db,
        account_id=account_id,
        generation=generation,
        character_id=character_id,
        fight_id=fight.id,
        context=context,
    )
    if ordinary.replayed:
        # Previously settled/legacy fight amounts are immutable, never scaled twice.
        return ordinary.policy
    totals = combat_rewards.load(db, character)
    scaled = scaled_policy(ordinary.policy, totals)
    snapshot = dict(
        algorithm=ALGORITHM,
        multiplier=MULTIPLIER,
        instance_id=run["instance_id"],
        fight_id=fight.id,
        character_id=character_id,
        xp=scaled.xp,
        kamas=scaled.kamas,
        ordinary_baseline=ordinary.snapshot,
        defeated_native_monsters=list(killed),
        eligible_character_ids=sorted(eligible_character_ids),
        limits=dict(
            xp_capped=scaled.xp < ordinary.policy.xp * MULTIPLIER,
            kamas_capped=scaled.kamas < ordinary.policy.kamas * MULTIPLIER,
        ),
    )
    encoded = json.dumps(
        snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf8")
    digest = sha256(encoded).hexdigest()
    updated = db.execute(
        "UPDATE fight_reward_policy_receipts SET snapshot=%s,snapshot_sha256=%s,xp=%s,kamas=%s "
        "WHERE fight_id=%s AND character_id=%s AND snapshot_sha256=%s",
        (
            Jsonb(snapshot),
            digest,
            scaled.xp,
            scaled.kamas,
            fight.id,
            character_id,
            ordinary.snapshot_sha256,
        ),
    )
    if updated.rowcount != 1:
        raise RuntimeError("Rift currency baseline changed before scaled settlement")
    return scaled
