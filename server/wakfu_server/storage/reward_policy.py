"""Versioned Dofus-reference reward math with Wakfu inputs stored in PostgreSQL.

This module does not discover a fight roster or attach itself to combat. The
caller supplies the authoritative terminal roster snapshot and leases the
transaction that will also write the existing fight reward receipt.
"""
from wakfu_server.reward_rates import MAX_REWARD_RATE_BP
from dataclasses import dataclass
from hashlib import sha256
import json
import secrets

from psycopg.pq import TransactionStatus
from psycopg.types.json import Jsonb


ALGORITHM = "starloco-formuleofficiel-xp-kamas-v1-wakfu-curve"
GROUP_BONUS = (0.5, 0.5, 2.1, 3.2, 4.3, 5.4, 6.5, 7.8, 9.0)
WISDOM_MIN, WISDOM_MAX = -500, 200


@dataclass(frozen=True)
class Decision:
    policy: object
    version: int
    snapshot: dict
    snapshot_sha256: str
    replayed: bool


def _integer(value, name, minimum=0, maximum=(1 << 63) - 1):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(f"Invalid {name}")
    return value


def _record(raw, *, name):
    if not isinstance(raw, dict):
        raise ValueError(f"Invalid {name}")
    return raw


def _normalize_context(context, character_id):
    context = _record(context, name="combat reward context")
    if set(context) - {"dungeon_rate_bp"} != {
        "winner_team",
        "winners",
        "losers",
        "challenge_percent",
        "star_percent",
    }:
        raise ValueError("Combat reward context has unknown or missing fields")
    winner_team = _integer(context["winner_team"], "winner team", 0, 1)
    challenge = _integer(context["challenge_percent"], "challenge percent", 0, 1000000)
    star = _integer(context["star_percent"], "star percent", 0, 1000000)
    winners_raw, losers_raw = context["winners"], context["losers"]
    if (
        not isinstance(winners_raw, list)
        or not winners_raw
        or not isinstance(losers_raw, list)
        or not losers_raw
    ):
        raise ValueError("Combat reward roster must contain both teams")

    winners = []
    recipient_present = False
    for raw in winners_raw:
        raw = _record(raw, name="winner")
        if set(raw) != {"level", "player", "eligible", "character_id", "wisdom"}:
            raise ValueError("Winner has unknown or missing fields")
        level = _integer(raw["level"], "winner level", 1, 200)
        for key in ("player", "eligible"):
            if type(raw[key]) is not bool:
                raise ValueError(f"Invalid winner {key}")
        cid = raw["character_id"]
        if cid is not None:
            cid = _integer(cid, "winner character id", 1)
            if cid == character_id:
                recipient_present = True
        if raw["player"] and cid is None:
            raise ValueError("Player winner is missing its character identity")
        wisdom = _integer(raw["wisdom"], "winner wisdom", WISDOM_MIN, WISDOM_MAX)
        winners.append(
            {
                "level": level,
                "player": raw["player"],
                "eligible": raw["eligible"],
                "character_id": cid,
                "wisdom": wisdom,
            }
        )
    if not recipient_present:
        raise ValueError("Reward recipient is absent from winner roster")

    losers = []
    for raw in losers_raw:
        raw = _record(raw, name="loser")
        if set(raw) != {"level", "monster_reference"}:
            raise ValueError("Loser has unknown or missing fields")
        level = _integer(raw["level"], "loser level", 1, 32767)
        ref = raw["monster_reference"]
        if ref is not None:
            ref = _integer(ref, "monster reference", 1, 2**31 - 1)
        losers.append({"level": level, "monster_reference": ref})
    normalized = {
        "winner_team": winner_team,
        "winners": winners,
        "losers": losers,
        "challenge_percent": challenge,
        "star_percent": star,
    }
    if "dungeon_rate_bp" in context:
        normalized["dungeon_rate_bp"] = _integer(
            context["dungeon_rate_bp"], "dungeon reward rate", 1, 71000
        )
    return normalized


def _trunc_div(numerator, denominator):
    """Java integer division, truncating toward zero."""
    if denominator <= 0:
        raise ValueError("Invalid integer division")
    return numerator // denominator


def _xp_amount_with_status(
    *, character_id, context, group_xp, xp_rate_bp, conquest_rate_bp, clamp_native=False
):
    """Port FormuleOfficiel math and report the local negative-XP clamp."""
    context = _normalize_context(context, character_id)
    group_xp = _integer(group_xp, "group XP")
    xp_rate_bp = _integer(xp_rate_bp, "XP rate", 0, MAX_REWARD_RATE_BP)
    conquest_rate_bp = _integer(conquest_rate_bp, "conquest rate", 0, 1000000)
    winners, losers = context["winners"], context["losers"]
    winner_level_sum = sum(row["level"] for row in winners)
    loser_level_sum = sum(row["level"] for row in losers)
    if winner_level_sum <= 0 or loser_level_sum <= 0:
        return 0, False

    level_max = max(winner_level_sum, loser_level_sum)
    level_min = min(winner_level_sum, loser_level_sum)
    group_ratio = level_max / level_min
    if group_ratio == 0:
        return 0, False
    group_ratio = 1.0 if group_ratio < 3.0 else 1.0 / group_ratio
    group_ratio = min(1.0, max(0.0, group_ratio))

    # Fight.java derives nbonus from player winners above one third of the
    # highest winning player level; level sums above still include every fighter.
    highest_winning_player_level = max(
        (w["level"] for w in winners if w["player"]), default=0
    )
    nbonus = sum(
        1
        for w in winners
        if w["player"] and w["level"] > highest_winning_player_level // 3
    )
    group_size = min(8, sum(1 for w in winners if w["player"] and w["eligible"]))
    if group_size < 1:
        return 0, False
    nbonus = min(8, nbonus)

    ratio = loser_level_sum / winner_level_sum
    if len(winners) == 1:
        ratio = 0.6
    elif ratio == 0:
        return 0
    elif 0.9 <= ratio <= 1.1:
        ratio = 1.0
    else:
        if ratio > 1:
            ratio = 1.0 / ratio
        ratio = max(0.01, ratio)

    recipient = next(w for w in winners if w["character_id"] == character_id)
    if not recipient["player"] or not recipient["eligible"]:
        return 0, False
    wisdom_factor = recipient["level"] * 0.5 + recipient["wisdom"]
    # Java's challenge/100 and star/100 are integer divisions. Likewise
    # groupXp/sizeGroupe truncates before the floating-point multiplication.
    challenge_factor = 1 + context["challenge_percent"] // 100
    star_factor = 1 + context["star_percent"] // 100
    divided_group_xp = _trunc_div(group_xp, group_size)
    value = (
        (1 + wisdom_factor / 100)
        * challenge_factor
        * star_factor
        * (GROUP_BONUS[nbonus] + ratio)
        * group_ratio
        * divided_group_xp
        * (xp_rate_bp / 10000)
        * (conquest_rate_bp / 10000)
        * (context.get("dungeon_rate_bp", 10000) / 10000)
    )
    if value < 0:
        # Wakemu reward receipts are nonnegative. Preserve a successful fight
        # finish and make this explicit policy adjustment auditable in snapshot.
        return 0, True
    if value >= 2**63:
        if clamp_native:
            return 2**63 - 1, False
        raise ValueError("XP reward exceeds signed64 range")
    # Java's positive double->long cast truncates toward zero. All validated
    # factors are nonnegative, so int(value) is equivalent here.
    return int(value), False


def xp_amount(*, character_id, context, group_xp, xp_rate_bp, conquest_rate_bp):
    """Return nonnegative XP using the versioned local Dofus-reference formula."""
    return _xp_amount_with_status(
        character_id=character_id,
        context=context,
        group_xp=group_xp,
        xp_rate_bp=xp_rate_bp,
        conquest_rate_bp=conquest_rate_bp,
    )[0]


def kamas_amount(
    *, minimum, maximum, kamas_rate_bp, roll_index=None, clamp_native=False
):
    """Use named inclusive bounds, correcting the reference caller's swapped args."""
    minimum = _integer(minimum, "minimum kamas", 0, 2**31 - 1)
    maximum = _integer(maximum, "maximum kamas", minimum, 2**31 - 1)
    rate = _integer(kamas_rate_bp, "kamas rate", 0, MAX_REWARD_RATE_BP)
    span = maximum - minimum + 1
    if roll_index is None:
        roll_index = secrets.randbelow(span)
    roll_index = _integer(roll_index, "kamas roll", 0, span - 1)
    amount = minimum + roll_index
    # Math.round for a nonnegative double is floor(x + 0.5).
    result = (amount * rate + 5000) // 10000
    if result >= 2**31:
        if clamp_native:
            return 2**31 - 1, roll_index
        raise ValueError("Fight report kamas exceed signed32 range")
    return result, roll_index


def _existing_decision(row):
    from wakfu_server.combat_rewards import Policy

    snapshot = row["snapshot"]
    encoded = json.dumps(
        snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf8")
    digest = sha256(encoded).hexdigest()
    if digest != row["snapshot_sha256"]:
        raise ValueError("Stored reward policy snapshot hash is invalid")
    if snapshot.get("xp") != row["xp"] or snapshot.get("kamas") != row["kamas"]:
        raise ValueError("Stored reward policy snapshot differs from its receipt")
    return Decision(
        Policy(xp=row["xp"], kamas=row["kamas"]),
        row["policy_version"],
        snapshot,
        digest,
        True,
    )


def resolve(
    store,
    db,
    *,
    account_id,
    generation,
    character_id,
    fight_id,
    context,
    kamas_roll_index=None,
):
    """Freeze one reward calculation inside the caller's durable award TX.

    `context` must be a complete terminal roster snapshot. Missing monster
    reference/level data fails closed instead of substituting unrelated data.
    """
    if db.info.transaction_status != TransactionStatus.INTRANS:
        raise ValueError("Reward policy requires an active transaction")
    account_id = _integer(account_id, "account id", 1)
    character_id = _integer(character_id, "character id", 1)
    fight_id = _integer(fight_id, "fight id", 1, 2**31 - 1)
    if not isinstance(generation, str) or not generation:
        raise ValueError("Invalid session generation")
    normalized = _normalize_context(context, character_id)
    from .combat_reward_ownership import lock_recipient

    lock_recipient(store, db, account_id, generation, character_id, fight_id)
    participant = db.execute(
        "SELECT p.team,f.status FROM combat_fight_participants p "
        "JOIN combat_fights f ON f.id=p.fight_id "
        "WHERE p.fight_id=%s AND p.character_id=%s AND p.account_id=%s FOR UPDATE OF f",
        (fight_id, character_id, account_id),
    ).fetchone()
    if (
        participant is None
        or participant["status"] != "finished"
        or participant["team"] != normalized["winner_team"]
    ):
        raise ValueError("Reward policy requires the own finished winning participant")

    current = db.execute(
        "SELECT * FROM fight_reward_policy_receipts WHERE fight_id=%s AND character_id=%s FOR UPDATE",
        (fight_id, character_id),
    ).fetchone()
    if current is not None:
        if current["account_id"] != account_id:
            raise ValueError("Reward policy receipt belongs to another account")
        return _existing_decision(current)

    # Migrations may encounter historical fight_rewards rows created before
    # this policy table existed. Their committed amounts remain authoritative.
    legacy = db.execute(
        "SELECT xp,kamas FROM fight_rewards WHERE fight_id=%s AND character_id=%s AND account_id=%s",
        (fight_id, character_id, account_id),
    ).fetchone()
    if legacy is not None:
        from wakfu_server.combat_rewards import Policy

        snapshot = {
            "algorithm": "existing-fight-reward-receipt",
            "fight_id": fight_id,
            "character_id": character_id,
            "xp": legacy["xp"],
            "kamas": legacy["kamas"],
        }
        encoded = json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode(
            "utf8"
        )
        return Decision(
            Policy(xp=legacy["xp"], kamas=legacy["kamas"]),
            0,
            snapshot,
            sha256(encoded).hexdigest(),
            True,
        )

    settings = db.execute(
        "SELECT v.version,v.xp_rate_bp,v.kamas_rate_bp,v.conquest_rate_bp "
        "FROM combat_reward_policy_active a JOIN combat_reward_policy_versions v ON v.version=a.version "
        "WHERE a.singleton=true FOR SHARE OF a,v"
    ).fetchone()
    if settings is None:
        raise ValueError("No active combat reward policy")

    catalog_values = []
    group_xp = 0
    minimum_kamas = maximum_kamas = 0
    for loser in normalized["losers"]:
        ref = loser["monster_reference"]
        if ref is None:
            continue
        row = db.execute(
            "SELECT base_xp,min_kamas,max_kamas,source FROM combat_reward_monster_levels "
            "WHERE monster_reference=%s AND monster_level=%s",
            (ref, loser["level"]),
        ).fetchone()
        source_kind = "reference_override"
        if row is None:
            row = db.execute(
                "SELECT base_xp,min_kamas,max_kamas,source FROM combat_reward_level_defaults "
                "WHERE monster_level=%s",
                (loser["level"],),
            ).fetchone()
            source_kind = "level_default"
        if row is None:
            raise ValueError(
                "Missing configured reward data for a defeated monster level"
            )
        group_xp += row["base_xp"]
        minimum_kamas += row["min_kamas"]
        maximum_kamas += row["max_kamas"]
        catalog_values.append(
            {
                "reference": ref,
                "level": loser["level"],
                "base_xp": row["base_xp"],
                "min_kamas": row["min_kamas"],
                "max_kamas": row["max_kamas"],
                "source": row["source"],
                "source_kind": source_kind,
            }
        )
    if group_xp >= 2**63 or maximum_kamas > 2**31 - 1:
        raise ValueError("Configured fight reward total exceeds native range")

    xp, negative_formula_clamped = _xp_amount_with_status(
        character_id=character_id,
        context=normalized,
        group_xp=group_xp,
        xp_rate_bp=settings["xp_rate_bp"],
        conquest_rate_bp=settings["conquest_rate_bp"],
        clamp_native=True,
    )
    kamas, roll = kamas_amount(
        minimum=minimum_kamas,
        maximum=maximum_kamas,
        kamas_rate_bp=settings["kamas_rate_bp"],
        roll_index=kamas_roll_index,
        clamp_native=True,
    )
    totals = db.execute(
        "SELECT p.xp,w.kamas FROM character_progression p "
        "JOIN characters c ON c.id=p.character_id "
        "JOIN account_wallets w ON w.account_id=c.account_id "
        "WHERE p.character_id=%s AND c.account_id=%s FOR UPDATE OF w,p",
        (character_id, account_id),
    ).fetchone()
    if totals is None:
        raise ValueError("Combat reward recipient totals are missing")
    calculated_xp, calculated_kamas = xp, kamas
    xp = min(xp, (2**63 - 1) - totals["xp"])
    kamas = min(kamas, (2**63 - 1) - totals["kamas"])
    snapshot = {
        "algorithm": ALGORITHM,
        "policy_version": settings["version"],
        "rates_bp": {
            "xp": settings["xp_rate_bp"],
            "kamas": settings["kamas_rate_bp"],
            "conquest": settings["conquest_rate_bp"],
        },
        "context": normalized,
        "monster_catalog": catalog_values,
        "group_xp": group_xp,
        "kamas_bounds": [minimum_kamas, maximum_kamas],
        "kamas_roll_index": roll,
        "xp": xp,
        "negative_formula_clamped": negative_formula_clamped,
        "native_limits": {
            "xp_at_packet_limit": calculated_xp == 2**63 - 1,
            "kamas_at_packet_limit": calculated_kamas == 2**31 - 1,
            "xp_storage_capped": xp < calculated_xp,
            "kamas_storage_capped": kamas < calculated_kamas,
        },
        "kamas": kamas,
    }
    encoded = json.dumps(
        snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf8")
    digest = sha256(encoded).hexdigest()
    inserted = db.execute(
        "INSERT INTO fight_reward_policy_receipts "
        "(fight_id,character_id,account_id,generation,policy_version,snapshot,snapshot_sha256,xp,kamas) "
        "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(fight_id,character_id) DO NOTHING",
        (
            fight_id,
            character_id,
            account_id,
            generation,
            settings["version"],
            Jsonb(snapshot),
            digest,
            xp,
            kamas,
        ),
    )
    persisted = db.execute(
        "SELECT * FROM fight_reward_policy_receipts WHERE fight_id=%s AND character_id=%s FOR UPDATE",
        (fight_id, character_id),
    ).fetchone()
    if persisted is None:
        raise RuntimeError("Reward policy receipt disappeared")
    decision = _existing_decision(persisted)
    if inserted.rowcount == 1:
        return Decision(
            decision.policy,
            decision.version,
            decision.snapshot,
            decision.snapshot_sha256,
            False,
        )
    return decision
