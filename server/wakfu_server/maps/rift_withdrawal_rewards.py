"""Pay earned Rift progress atomically when an owner explicitly surrenders.

The live fight and the remaining players retain their outcome and actors. The
ordinary fight/character receipt keys prevent another payout at terminal exit.
"""
from copy import copy


def settle(store, db, fight, *, owner_ids):
    from psycopg.pq import TransactionStatus
    from wakfu_server import rift_runtime, rift_rewards, rift_currency_rewards
    from wakfu_server import combat_rewards
    from wakfu_server.combat_encounter_roles import assigned_roles
    from wakfu_server.rift_earned_rewards import defeated_sources
    from wakfu_server.combat_reward_ownership import _rift_withdrawal_scope

    if getattr(fight, "rift_wave_state", None) is None or fight.phase == "placement":
        return {}
    if db.info.transaction_status != TransactionStatus.INTRANS:
        raise ValueError("Rift withdrawal requires its surrender transaction")
    if fight.phase not in ("placement", "active"):
        raise ValueError("Only a live Rift can settle surrendered progress")
    durable = db.execute(
        "SELECT status,fight_kind FROM combat_fights WHERE id=%s FOR UPDATE",
        (fight.id,),
    ).fetchone()
    if (
        durable is None
        or durable["status"] not in ("placement", "active")
        or durable["fight_kind"] != "pve"
    ):
        raise ValueError("Rift withdrawal no longer owns a live PvE fight")
    run = rift_runtime._run(db, fight.rift_wave_state["instance_id"])
    if (
        run["status"] == "entered"
        and run["fight_id"] is None
        and fight.phase == "placement"
    ):
        return {}
    rift_runtime.persist_progress(db, fight)
    run = rift_runtime._run(db, fight.rift_wave_state["instance_id"])
    if run["status"] != "running" or run["fight_id"] != fight.id:
        raise ValueError("Rift withdrawal differs from its durable run")
    rows = tuple(
        db.execute(
            "SELECT p.character_id,p.account_id,p.team,p.session_generation,"
            "EXISTS(SELECT 1 FROM combat_pve_withdrawals w WHERE "
            "w.fight_id=p.fight_id AND w.character_id=p.character_id) AS withdrawn "
            "FROM combat_fight_participants p WHERE p.fight_id=%s "
            "ORDER BY p.character_id FOR UPDATE OF p",
            (fight.id,),
        )
    )
    roles = assigned_roles(fight)
    if {row["character_id"] for row in rows} != set(run["members"]):
        raise ValueError("Rift withdrawal differs from frozen membership")
    owners = frozenset(owner_ids)
    if not owners or owners - {row["account_id"] for row in rows}:
        raise ValueError("Unknown surrendering Rift owner")
    for row in rows:
        actor = fight.actors.get(row["character_id"])
        if (
            actor is None
            or not actor.controlled
            or actor.owner_id != row["account_id"]
            or actor.team != row["team"]
            or actor.team != roles.player_team
        ):
            raise ValueError("Rift surrender actor differs from durable participant")
    members = tuple(
        row for row in rows if row["account_id"] in owners and not row["withdrawn"]
    )
    if not members or not defeated_sources(db, fight, run):
        return {}
    for row in members:
        if getattr(fight.actors[row["character_id"]], "pve_withdrawn", False):
            raise ValueError("Rift surrender must use the original live actors")
        if (
            db.execute(
                "SELECT id FROM characters WHERE id=%s AND account_id=%s AND deleted_at IS NULL FOR UPDATE",
                (row["character_id"], row["account_id"]),
            ).fetchone()
            is None
        ):
            raise ValueError("Rift surrender member is unavailable")
    result = dict(
        outcome="lost",
        completed_waves=run["completed_waves"],
        defeated_monsters=run["defeated_monsters"],
        reached_wave=run["wave"],
        turn=fight.native_timeline_round,
    )
    view = copy(fight)
    view.phase, view.winner = "finished", roles.npc_team
    eligible = tuple(row["character_id"] for row in rows if not row["withdrawn"])
    rewards = {}
    with _rift_withdrawal_scope(db, view, members, result):
        rift_rewards.apply(
            db,
            run,
            result,
            store=store,
            eligible_character_ids=tuple(row["character_id"] for row in members),
            fight=view,
        )
        for row in members:
            identity, owner, generation = (
                row["character_id"],
                row["account_id"],
                row["session_generation"],
            )
            character = store.character(owner, identity, db)
            policy = rift_currency_rewards.resolve(
                store,
                db,
                account_id=owner,
                generation=generation,
                character_id=identity,
                fight=view,
                character=character,
                eligible_character_ids=eligible,
            )
            rewards[identity] = combat_rewards.award_shared_member(
                store,
                db,
                owner,
                generation,
                identity,
                view,
                policy,
            )
    return rewards


def return_packets(store, db, fight, character):
    """Refresh the earned wallet and inventory after native withdrawal cleanup."""
    if getattr(fight, "rift_wave_state", None) is None:
        return []
    from wakfu_server import rift_rewards, wire
    from wakfu_server.combat_rewards import load
    import struct

    rewards = tuple(
        db.execute(
            "SELECT * FROM fight_rewards WHERE fight_id=%s AND account_id=%s ORDER BY character_id",
            (fight.id, character["account_id"]),
        )
    )
    if not rewards:
        return []
    from wakfu_server.combat_lifecycle import outside_progression

    total = load(db, character)
    packets = [
        (13021, struct.pack(">q", total["kamas"])),
        (13873, wire.account_kamas(total["kamas"])),
    ]
    for row in rewards:
        if row["character_id"] != character["id"]:
            hero = store.character(character["account_id"], row["character_id"], db)
            packets.append(outside_progression(hero))
        packets.extend(
            rift_rewards.delivery(
                db, store, fight.rift_wave_state["instance_id"], row["character_id"]
            )["packets"]
        )
    return packets
