"""Startup-only earned exits from committed checkpoints, never resumed combat.

The caller owns the startup abort transaction before any listener exists. Only
currently active fights qualify; an old administrative abort is not evidence of
an interruption. All reward calculations and receipts use the surrender path.
"""
from types import SimpleNamespace
from copy import deepcopy

from psycopg.types.json import Jsonb

POLICY = "wakemu.rift.startup-checkpoint-earned-exit.v1"


def _integer_keys(mapping):
    if not isinstance(mapping, dict):
        raise ValueError("Missing checkpoint identity map")
    result = {}
    for key, value in mapping.items():
        identity = int(key)
        if str(identity) != str(key) or identity in result:
            raise ValueError("Ambiguous checkpoint identity")
        result[identity] = value
    return result


def checkpoint_evidence(db, run, checkpoint):
    """Validate a read-only accounting projection; do not restore a native FSM."""
    from wakfu_server.rift_earned_rewards import defeated_sources
    from wakfu_server.combat_encounter_roles import assigned_roles

    # Only accounting fields are interpreted. Native effect containers are not
    # reconstructed or replayed merely to recover an earned exit.
    raw = deepcopy(checkpoint["snapshot"])
    if not isinstance(raw, dict):
        raise ValueError("Missing checkpoint state")
    state = raw.get("rift_wave_state")
    if (
        raw.get("id") != run["fight_id"]
        or raw.get("phase") not in ("placement", "active", "finished")
        or not isinstance(state, dict)
        or state.get("instance_id") != run["instance_id"]
        or state.get("wave") != run["wave"]
        or type(raw.get("native_timeline_round")) is not int
        or raw["native_timeline_round"] < run["last_turn"]
    ):
        raise ValueError("Checkpoint differs from its active durable Rift")
    if raw["phase"] == "finished" and (
        type(raw.get("winner")) is not int
        or raw["winner"] not in (0, 1)
        or state.get("outcome") in ("capacity_exhausted", "administrative_victory")
    ):
        raise ValueError("Missing natural terminal Rift checkpoint outcome")
    actors = {}
    for identity, record in _integer_keys(raw.get("actors")).items():
        if not isinstance(record, dict) or record.get("id") != identity:
            raise ValueError("Checkpoint actor identity differs")
        actor = SimpleNamespace(**record)
        if (
            type(actor.hp) is not int
            or type(actor.max_hp) is not int
            or not 0 <= actor.hp <= actor.max_hp
            or type(actor.controlled) is not bool
        ):
            raise ValueError("Invalid checkpoint actor health or ownership")
        for field in (
            "effect_stats",
            "effect_maxima",
            "effect_minima",
            "effect_base_maxima",
            "effect_base_minima",
            "effect_percentages",
            "effect_characteristic_raw_currents",
            "effect_resource_raw_currents",
        ):
            values = getattr(actor, field, None)
            if values is not None:
                setattr(actor, field, _integer_keys(values))
        if getattr(actor, "effect_frozen", None) is not None:
            actor.effect_frozen = frozenset(actor.effect_frozen)
        actor.position = tuple(actor.position)
        actors[identity] = actor
    fight = SimpleNamespace(**raw)
    fight.actors = actors
    fight.rift_monsters = _integer_keys(raw.get("rift_monsters"))
    # This checks the frozen role policy, canonical actor/species bindings,
    # original non-summon actors, source levels and every admitted wave.
    killed = defeated_sources(db, fight, run)
    if fight.phase == "placement" and (
        killed
        or run["wave"] != 1
        or run["completed_waves"] != 0
        or run["defeated_monsters"] != 0
        or run["last_turn"] != 0
    ):
        # Ready can commit durable active status before its first checkpoint.
        # A placement projection certifies only an empty exit, never rewards.
        raise ValueError("Placement checkpoint cannot certify earned progress")
    roles = assigned_roles(fight)
    members = tuple(
        db.execute(
            "SELECT p.*,EXISTS(SELECT 1 FROM combat_pve_withdrawals w "
            "WHERE w.fight_id=p.fight_id AND w.character_id=p.character_id) AS withdrawn "
            "FROM combat_fight_participants p WHERE p.fight_id=%s "
            "ORDER BY p.account_id,p.character_id FOR UPDATE OF p",
            (fight.id,),
        )
    )
    if {row["character_id"] for row in members} != set(run["members"]):
        raise ValueError("Checkpoint differs from frozen Rift membership")
    withdrawals = {
        row["character_id"]: row
        for row in db.execute(
            "SELECT w.*,e.reason AS health_reason,e.generation AS health_generation "
            "FROM combat_pve_withdrawals w LEFT JOIN fight_health_exits e "
            "ON e.fight_id=w.fight_id AND e.character_id=w.character_id "
            "WHERE w.fight_id=%s ORDER BY w.character_id FOR UPDATE OF w",
            (fight.id,),
        )
    }
    withdrawn_owners = {row["account_id"] for row in members if row["withdrawn"]}
    for row in members:
        actor = actors.get(row["character_id"])
        if (
            actor is None
            or not actor.controlled
            or actor.owner_id != row["account_id"]
            or actor.team != row["team"]
            or actor.team != roles.player_team
            or (bool(getattr(actor, "pve_withdrawn", False)) and not row["withdrawn"])
        ):
            raise ValueError("Checkpoint player differs from durable participant")
        if row["account_id"] not in withdrawn_owners:
            continue
        receipt = withdrawals.get(row["character_id"])
        if (
            receipt is None
            or receipt["account_id"] != row["account_id"]
            or receipt["health_reason"] != "abort"
            or receipt["health_generation"] != row["session_generation"]
            or not receipt["session_generation"]
            or (
                receipt["session_generation"] != row["session_generation"]
                and receipt["returned_at"] is None
            )
        ):
            raise ValueError("Withdrawal lacks owned original-generation health proof")
        # Withdrawal commits wounds, earned rewards and exclusion together,
        # before adopting its detached candidate. A later checkpoint need not
        # exist. Only this accounting projection uses the durable exclusion.
        actor.pve_withdrawn = True
    return fight, members, killed


def _settle_terminal_checkpoint(store, db, fight, run, members):
    """Settle committed terminal accounting without replaying native reactions."""
    from wakfu_server import combat_rewards, rift_currency_rewards, rift_rewards
    from wakfu_server import rift_runtime
    from wakfu_server.combat_encounter_roles import assigned_roles
    from wakfu_server.combat_reward_ownership import (
        _durable_settlement_scope,
        is_earned_rift_recipient,
    )

    roles = assigned_roles(fight)
    if (
        fight.phase != "finished"
        or type(fight.winner) is not int
        or fight.winner not in (roles.player_team, roles.npc_team)
        or fight.rift_wave_state.get("outcome")
        in ("capacity_exhausted", "administrative_victory")
    ):
        raise ValueError("Missing natural terminal Rift checkpoint authority")
    for member in members:
        if (
            db.execute(
                "SELECT id FROM characters WHERE id=%s AND account_id=%s "
                "AND deleted_at IS NULL FOR UPDATE",
                (member["character_id"], member["account_id"]),
            ).fetchone()
            is None
        ):
            raise ValueError("Terminal Rift participant is unavailable")
    eligible = tuple(row for row in members if not row["withdrawn"])
    eligible_ids = tuple(row["character_id"] for row in eligible)
    # Same locked roster and actual outcome as normal terminal settlement.
    # This startup transaction owns the interrupted durable active fight.
    db.execute("UPDATE combat_fights SET status='finished' WHERE id=%s", (fight.id,))
    with _durable_settlement_scope(db, fight, members):
        receipt = rift_runtime.settle(
            db,
            run["instance_id"],
            fight.id,
            outcome="won" if fight.winner == roles.player_team else "lost",
            turn=fight.native_timeline_round,
            reconcile_earned_rewards=True,
            apply_rewards=lambda reward_db, current, result: rift_rewards.apply(
                reward_db,
                current,
                result,
                store=store,
                eligible_character_ids=eligible_ids,
                fight=fight,
            ),
        )
        for member in eligible:
            owner, identity, generation = (
                member[key]
                for key in ("account_id", "character_id", "session_generation")
            )
            if fight.actors[
                identity
            ].team != fight.winner and not is_earned_rift_recipient(
                db, fight, owner, generation, identity
            ):
                continue  # A zero-kill defeated owner has no earned reward authority.
            character = store.character(owner, identity, db)
            policy = rift_currency_rewards.resolve(
                store,
                db,
                account_id=owner,
                generation=generation,
                character_id=identity,
                fight=fight,
                character=character,
                eligible_character_ids=eligible_ids,
            )
            combat_rewards.award_shared_member(
                store, db, owner, generation, identity, fight, policy
            )
        from wakfu_server.characters.companions import settle_rewards

        settle_rewards(db, store, fight)
    return receipt


def settle_startup(store, db):
    """Pay certified interrupted progress inside the caller's abort transaction."""
    from psycopg.pq import TransactionStatus
    from wakfu_server import combat_health, rift_runtime
    from wakfu_server.rift_withdrawal_rewards import settle
    from wakfu_server.fight_checkpoint_store import checkpoint_digest
    from wakfu_server.characters.companions import settle_owner_exit

    if db.info.transaction_status != TransactionStatus.INTRANS:
        raise ValueError("Startup Rift recovery requires the abort transaction")
    candidates = tuple(
        db.execute(
            "SELECT r.instance_id,f.id AS fight_id,c.revision,c.status AS checkpoint_status,"
            "c.snapshot FROM combat_fights f JOIN rift_instances r ON r.fight_id=f.id "
            "LEFT JOIN fight_checkpoints c ON c.fight_id=f.id "
            "WHERE f.status='active' AND f.fight_kind='pve' AND r.status='running' "
            "ORDER BY f.id FOR UPDATE OF f,r",
        )
    )
    for candidate in candidates:
        fight_id, revision = candidate["fight_id"], candidate["revision"]
        try:
            if candidate["checkpoint_status"] != "active":
                raise ValueError("Missing active checkpoint")
            # Checkpoints are locked separately because the outer join permits
            # detecting missing evidence instead of silently forfeiting it.
            db.execute(
                "SELECT fight_id FROM fight_checkpoints WHERE fight_id=%s FOR UPDATE",
                (fight_id,),
            )
            run = rift_runtime._run(db, candidate["instance_id"])
            fight, members, killed = checkpoint_evidence(db, run, candidate)
            if not killed and fight.phase != "finished":
                continue
            eligible = tuple(row for row in members if not row["withdrawn"])
            for row in () if fight.phase == "finished" else eligible:
                owner, identity = row["account_id"], row["character_id"]
                baseline = {
                    key: row["entry_" + key]
                    for key in ("hp", "max_hp", "hp_damage", "health_dead")
                }
                if any(value is None for value in baseline.values()):
                    raise ValueError("Missing participant entry health baseline")
                lease = db.execute(
                    "SELECT generation,character_id FROM sessions "
                    "WHERE account_id=%s FOR UPDATE",
                    (owner,),
                ).fetchone()
                main_id = identity if lease is None else lease["character_id"]
                character = store.character(owner, identity, db)
                character.update(baseline)
                combat_health.persist(
                    store,
                    owner,
                    row["session_generation"],
                    character,
                    fight,
                    reason="abort",
                    db=db,
                    disconnected_baseline=baseline,
                    session_character_id=main_id,
                )
            if fight.phase != "finished":
                for owner in sorted({row["account_id"] for row in eligible}):
                    settle_owner_exit(db, store, fight, owner)
            if fight.phase == "finished":
                receipt = _settle_terminal_checkpoint(store, db, fight, run, members)
            else:
                if eligible:
                    settle(
                        store,
                        db,
                        fight,
                        owner_ids={row["account_id"] for row in eligible},
                    )
                receipt = rift_runtime.settle(
                    db,
                    run["instance_id"],
                    fight.id,
                    outcome="closed",
                    turn=fight.native_timeline_round,
                    apply_rewards=None,
                )
            provenance = dict(
                policy=POLICY,
                reason="startup_interruption",
                checkpoint_phase=fight.phase,
                checkpoint_winner=getattr(fight, "winner", None),
                checkpoint_revision=revision,
                checkpoint_sha256=checkpoint_digest(candidate["snapshot"]),
                defeated_actor_ids=sorted(source["id"] for source in killed),
                recipient_ids=sorted(row["character_id"] for row in eligible),
            )
            db.execute(
                "UPDATE rift_settlement_receipts SET result=%s WHERE instance_id=%s",
                (
                    Jsonb(dict(receipt["result"], recovery=provenance)),
                    run["instance_id"],
                ),
            )
        except Exception as error:
            raise ValueError(
                f"Interrupted Rift {fight_id} checkpoint {revision} remains pending: "
                f"{type(error).__name__}: {error}"
            ) from error
