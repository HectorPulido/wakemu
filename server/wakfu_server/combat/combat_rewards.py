"""Explicit local victory rewards, independent of official reward/drop data.

Award keys are durable fight/character identities, independent of session
replacement. PostgreSQL migrations own the schema. No item loot is generated.
"""
from dataclasses import dataclass
from contextlib import nullcontext
from psycopg.pq import TransactionStatus
from .progression import level_xp, XP_BY_LEVEL


@dataclass(frozen=True)
class Policy:
    xp: int = 0
    kamas: int = 0

    def __post_init__(self):
        for amount in (self.xp, self.kamas):
            if type(amount) is not int or not 0 <= amount < 2**63:
                raise ValueError("Invalid local reward amount")
        if self.kamas >= 2**31:
            raise ValueError("FightReport gainedKamas requires signed32 amount")


def load(db, character):
    """Read authoritative XP and account currency; initialization is explicit."""
    row = db.execute(
        "SELECT p.xp,w.kamas FROM character_progression p "
        "JOIN account_wallets w ON w.account_id=%s WHERE p.character_id=%s",
        (character["account_id"], character["id"]),
    ).fetchone()
    if row is None:
        raise ValueError("Missing character progression or account wallet")
    return dict(row)


def award(
    store,
    account_id,
    generation,
    character_id,
    fight,
    policy=Policy(),
    *,
    db=None,
    _durable_member=False,
):
    """Award a winning controlled participant once, under the current lease.

    Returns {character, awarded, xp, kamas}; character contains updated total
    xp/kamas and level. xp/kamas at the top level are this fight's amounts.
    Level-dependent health is refreshed in the same transaction as the award.
    """
    if not isinstance(policy, Policy):
        raise ValueError("Explicit local reward Policy required")
    actor = fight.actors.get(character_id)
    if (
        fight.phase != "finished"
        or fight.winner not in (0, 1)
        or actor is None
        or not actor.controlled
        or actor.owner_id != account_id
        or actor.team != fight.winner
    ):
        raise ValueError("Rewards require the own winning fight participant")
    if type(fight.id) is not int or not 0 < fight.id < 2**31:
        raise ValueError("Invalid reward fight identity")
    borrowed = db is not None
    if borrowed and db.info.transaction_status != TransactionStatus.INTRANS:
        raise ValueError("Reward requires an active transaction")
    if _durable_member and not borrowed:
        raise ValueError(
            "Shared participant reward requires the settlement transaction"
        )
    with nullcontext(db) if borrowed else store.connection() as db:
        participant = db.execute(
            "SELECT p.team,p.session_generation,f.status,f.fight_kind "
            "FROM combat_fight_participants p JOIN combat_fights f ON f.id=p.fight_id "
            "WHERE p.fight_id=%s AND p.character_id=%s AND p.account_id=%s FOR UPDATE OF f",
            (fight.id, character_id, account_id),
        ).fetchone()
        if (
            participant is None
            or participant["fight_kind"] != "pve"
            or participant["team"] != fight.winner
            or participant["status"] != "finished"
            or (_durable_member and participant["session_generation"] != generation)
        ):
            raise ValueError("Missing finished owned durable fight participant")
        if not _durable_member:
            store.lock_character(db, account_id, generation, character_id)
        db.execute(
            "SELECT account_id FROM account_wallets WHERE account_id=%s FOR UPDATE",
            (account_id,),
        )
        character = store.character(account_id, character_id, db)
        totals = load(db, character)
        existing = db.execute(
            "SELECT * FROM fight_rewards WHERE fight_id=%s AND character_id=%s",
            (fight.id, character_id),
        ).fetchone()
        if existing is not None:
            return dict(
                character={**character, **totals},
                awarded=False,
                xp=existing["xp"],
                kamas=existing["kamas"],
                xp_info=_xp_info(existing),
            )
        xp, kamas = totals["xp"] + policy.xp, totals["kamas"] + policy.kamas
        if max(xp, kamas) >= 2**63:
            raise ValueError("Reward total exceeds native signed64 storage")
        level = max(
            character["level"],
            max(level for level, threshold in XP_BY_LEVEL.items() if threshold <= xp),
        )
        db.execute(
            "UPDATE character_progression SET xp=%s WHERE character_id=%s",
            (xp, character_id),
        )
        db.execute(
            "UPDATE account_wallets SET kamas=%s WHERE account_id=%s",
            (kamas, account_id),
        )
        db.execute(
            "UPDATE characters SET level=%s WHERE account_id=%s AND id=%s",
            (level, account_id, character_id),
        )
        if level != character["level"]:
            if _durable_member:
                _initialize_health_for_durable_member(
                    store, db, account_id, character_id
                )
            else:
                from . import health_store

                health_store.initialize(
                    store, account_id, generation, character_id, db=db
                )
        db.execute(
            "INSERT INTO fight_rewards(generation,fight_id,character_id,account_id,xp,kamas,created_at,start_xp,end_xp,start_level,end_level) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                generation,
                fight.id,
                character_id,
                account_id,
                policy.xp,
                policy.kamas,
                store.now(),
                totals["xp"],
                xp,
                character["level"],
                level,
            ),
        )
        return dict(
            character={
                **store.character(account_id, character_id, db),
                "xp": xp,
                "kamas": kamas,
            },
            awarded=True,
            xp=policy.xp,
            kamas=policy.kamas,
            xp_info=dict(
                end_xp=xp,
                won_xp=policy.xp,
                start_level=character["level"],
                end_level=level,
            ),
        )


def award_shared_member(
    store, db, account_id, joined_generation, character_id, fight, policy
):
    """Apply a shared-fight award to its durable member inside settlement.

    The finalizer's current lease authorizes the complete roster settlement.
    A disconnected teammate is still paid against its recorded join generation;
    this helper never accepts a client request and requires the settlement TX.
    """
    if db.info.transaction_status != TransactionStatus.INTRANS:
        raise ValueError("Shared participant reward requires an active transaction")
    return award(
        store,
        account_id,
        joined_generation,
        character_id,
        fight,
        policy,
        db=db,
        _durable_member=True,
    )


def _initialize_health_for_durable_member(store, db, account_id, character_id):
    """Reconfigure level-derived HP without requiring an offline session lease."""
    from wakfu_server.characters import health_policy, health_store
    from .equipment_stats import effective_character

    character = store.character(account_id, character_id, db)
    maximum = effective_character(character)["max_hp"]
    hp = health_policy.reconfigure(db, character, maximum)
    now = health_store.timestamp(int(store.clock() * 1000))
    db.execute(
        "INSERT INTO character_regeneration(character_id,initial_hp,started_at,coefficient,last_at) "
        "VALUES(%s,%s,%s,0,%s) ON CONFLICT(character_id) DO UPDATE SET "
        "initial_hp=excluded.initial_hp,started_at=excluded.started_at,coefficient=0,last_at=excluded.last_at",
        (character_id, hp, now, now),
    )


def wallet(store, account_id):
    """Read the single account balance; registration initializes the wallet."""
    with store.connection() as db:
        row = db.execute(
            "SELECT kamas FROM account_wallets WHERE account_id=%s", (account_id,)
        ).fetchone()
        if row is None:
            raise ValueError("Unknown account wallet")
        return row["kamas"]


def _xp_info(receipt):
    if receipt["xp"] == 0:
        return None
    if any(receipt[key] is None for key in ("end_xp", "start_level", "end_level")):
        raise ValueError("Legacy reward has no authoritative XP receipt")
    return dict(
        end_xp=receipt["end_xp"],
        won_xp=receipt["xp"],
        start_level=receipt["start_level"],
        end_level=receipt["end_level"],
    )


def report_metadata(metadata, character_id, reward):
    """Attach a committed award receipt to an existing own player report record."""
    if (
        reward["character"]["id"] != character_id
        or metadata.get(character_id, {}).get("kind") != "player"
    ):
        raise ValueError("Reward receipt does not match report participant")
    result = {identity: dict(record) for identity, record in metadata.items()}
    result[character_id]["gained_kamas"] = reward["kamas"]
    if reward["xp"]:
        if not reward.get("xp_info"):
            raise ValueError("Missing authoritative XP receipt")
        result[character_id]["xp_info"] = dict(reward["xp_info"])
    return result
