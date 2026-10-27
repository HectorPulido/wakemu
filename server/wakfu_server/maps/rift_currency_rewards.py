"""Exactly-once earned Rift XP/kamas: normal reward times reached wave times10.

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
from wakfu_server.combat_encounter_roles import assigned_roles

ALGORITHM = "rift-reached-wave-times-ten-ordinary-xp-kamas-v1"


def reward_context(fight, character, run, rosters, eligible_character_ids):
    """Compare accumulated native sources with every durable admitted wave.

    Count only defeated original enemies, including kills from the unfinished
    final wave. Summons, living enemies and merely planned waves never pay.
    """
    from wakfu_server.rift_earned_rewards import defeated_sources

    killed = defeated_sources(None, fight, run, rosters=rosters)
    from wakfu_server.combat_companions import registered_companion_ids

    companion_ids = registered_companion_ids(fight)
    roles = assigned_roles(fight)
    eligible = tuple(eligible_character_ids)
    if len(set(eligible)) != len(eligible) or any(
        type(cid) is not int or cid not in run["members"] for cid in eligible
    ):
        raise ValueError("Rift reward eligibility differs from frozen membership")
    winners = {
        identity: actor
        for identity, actor in fight.actors.items()
        if actor.controlled
        and actor.team == roles.player_team
        and not combat_reward_context._summon(actor)
        and not getattr(actor, "pve_withdrawn", False)
    }
    if set(winners) - companion_ids != set(eligible) or character["id"] not in eligible:
        raise ValueError("Rift reward eligibility differs from actual participants")
    if not killed:
        return None, ()
    view = SimpleNamespace(
        phase="finished",
        winner=roles.player_team,
        native_encounter_roles=getattr(fight, "native_encounter_roles", None),
        native_companion_sources={
            str(identity): fight.native_companion_sources[str(identity)]
            for identity in companion_ids
            if identity in winners
        },
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


def scaled_policy(baseline, totals, multiplier):
    """Apply the multiplier after ordinary rounding, then native/storage caps."""
    if type(multiplier) is not int or not 1 <= multiplier <= 100000:
        raise ValueError("Invalid earned Rift reward multiplier")
    return combat_rewards.Policy(
        xp=min(baseline.xp * multiplier, (2**63 - 1) - totals["xp"]),
        kamas=min(
            baseline.kamas * multiplier, 2**31 - 1, (2**63 - 1) - totals["kamas"]
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
    roles = assigned_roles(fight)
    outcome = "won" if fight.winner == roles.player_team else "lost"
    if (
        receipt["outcome"] not in ("won", "lost")
        or state.get("outcome") in ("capacity_exhausted", "administrative_victory")
        or actor is None
        or actor.team != roles.player_team
        or getattr(actor, "pve_withdrawn", False)
    ):
        return combat_rewards.Policy()
    if (
        fight.phase != "finished"
        or receipt["outcome"] != outcome
        or run["status"] != outcome
        or (
            outcome == "won"
            and receipt["result"]["turn"] < run["policy"]["turn_budget"]
        )
        or character["id"] != character_id
        or character["account_id"] != account_id
    ):
        raise ValueError("Rift currency reward survival or recipient is invalid")
    from wakfu_server.combat_reward_ownership import (
        lock_recipient,
        is_earned_rift_recipient,
    )

    if outcome == "lost" and not is_earned_rift_recipient(
        db, fight, account_id, generation, character_id
    ):
        raise ValueError("Rift defeat reward lacks its earned settlement capability")

    lock_recipient(store, db, account_id, generation, character_id, fight.id)
    old = db.execute(
        "SELECT * FROM fight_reward_policy_receipts WHERE fight_id=%s AND character_id=%s FOR UPDATE",
        (fight.id, character_id),
    ).fetchone()
    if old is not None:
        if old["account_id"] != account_id:
            raise ValueError("Rift currency receipt belongs to another account")
        return reward_policy._existing_decision(old).policy
    from wakfu_server.rift_wave_bindings import rosters as bound_rosters

    rosters = bound_rosters(db, run, fight=fight)
    from wakfu_server.combat_companions import validate_durable_roster

    validate_durable_roster(db, fight)
    context, killed = reward_context(
        fight, character, run, rosters, eligible_character_ids
    )
    if context is None:
        return combat_rewards.Policy()
    from wakfu_server.rift_earned_rewards import frozen_factor

    factor = frozen_factor(db, run, receipt["result"])
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
    scaled = scaled_policy(ordinary.policy, totals, factor["multiplier"])
    snapshot = dict(
        algorithm=ALGORITHM,
        multiplier=factor["multiplier"],
        factor_policy=factor,
        outcome=outcome,
        instance_id=run["instance_id"],
        fight_id=fight.id,
        character_id=character_id,
        xp=scaled.xp,
        kamas=scaled.kamas,
        ordinary_baseline=ordinary.snapshot,
        defeated_native_monsters=list(killed),
        eligible_character_ids=sorted(eligible_character_ids),
        limits=dict(
            xp_capped=scaled.xp < ordinary.policy.xp * factor["multiplier"],
            kamas_capped=scaled.kamas < ordinary.policy.kamas * factor["multiplier"],
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
