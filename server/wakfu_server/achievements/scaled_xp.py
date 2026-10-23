"""Freeze native reward17 XP at earning, independently of combat XP policy."""
import math

from psycopg.pq import TransactionStatus
from psycopg.types.json import Jsonb
from wakfu_server.wakfu_xp import MAX_XP, monster_base_xp

POLICY = "wakemu.achievement-native17-base-no-subscription-v1"
FORMULA = "native-monster-base-real-level-percent-java-round"


def _payload(payload):
    if (
        type(payload) is not dict
        or type(payload.get("aeV")) is not int
        or payload["aeV"] != 17
        or type(payload.get("d")) is not int
        or not 0 < payload["d"] < 2**31
        or type(payload.get("ckk")) is not bool
        or not isinstance(payload.get("ckl"), (list, tuple))
        or len(payload["ckl"]) != 1
        or type(payload["ckl"][0]) is not int
        or not 0 < payload["ckl"][0] < 2**31
    ):
        raise ValueError("Invalid native scaled XP reward")
    return payload["ckl"][0]


def _key(character_id, achievement_id, cycle_key, reward_key, payload):
    from .storage import _key as text_key

    if (
        type(character_id) is not int
        or not 0 < character_id < 2**63
        or type(achievement_id) is not int
        or not 0 < achievement_id < 2**31
    ):
        raise ValueError("Invalid scaled XP entitlement owner")
    text_key(cycle_key)
    text_key(reward_key)
    if reward_key != str(payload["d"]):
        raise ValueError("Scaled XP native reward identity mismatch")
    return character_id, achievement_id, cycle_key, reward_key


def _same(left, right):
    from .storage import _json

    return _json(left) == _json(right)


def _rounded(parameter, base):
    """Java Math.round(double), including signed64 saturation, for positive XP."""
    value = parameter / 100.0 * base
    if value >= 2**63:
        return MAX_XP
    # Above 2**52 every representable double is already integral; adding .5
    # would introduce a second rounding that Java Math.round avoids.
    return math.floor(value if value >= 2**52 else value + 0.5)


def reserve(db, character_id, achievement_id, cycle_key, reward_key, payload):
    """Freeze after the caller enqueues the exact original outbox payload.

    Replay validates existing earned facts before consulting today's policy or
    level. The caller must roll back the whole transaction if reservation fails.
    """
    if db.info.transaction_status != TransactionStatus.INTRANS:
        raise ValueError("Scaled XP reservation requires an owned transaction")
    parameter = _payload(payload)
    key = _key(character_id, achievement_id, cycle_key, reward_key, payload)
    outbox = db.execute(
        "SELECT payload FROM character_achievement_reward_outbox "
        "WHERE character_id=%s AND achievement_id=%s AND cycle_key=%s AND reward_key=%s FOR UPDATE",
        key,
    ).fetchone()
    if outbox is None or not _same(outbox["payload"], payload):
        raise ValueError("Missing exact scaled XP outbox reservation")
    previous = db.execute(
        "SELECT * FROM achievement_scaled_xp_receipts "
        "WHERE character_id=%s AND achievement_id=%s AND cycle_key=%s AND reward_key=%s",
        key,
    ).fetchone()
    if previous is not None:
        if (
            not _same(previous["payload"], payload)
            or previous["native_parameter"] != parameter
        ):
            raise ValueError("Scaled XP earned identity changed")
        return dict(previous)
    active = db.execute(
        "SELECT p.* FROM achievement_scaled_xp_active a "
        "JOIN achievement_scaled_xp_policies p USING(policy_version) WHERE a.singleton AND a.enabled"
    ).fetchone()
    if (
        active is None
        or active["policy_version"] != POLICY
        or active["formula"] != FORMULA
        or active["subscription_factor"] != 1
    ):
        raise ValueError("Native scaled XP policy is not enabled or supported")
    owner = db.execute(
        "SELECT level FROM characters WHERE id=%s AND deleted_at IS NULL FOR UPDATE",
        (character_id,),
    ).fetchone()
    if owner is None:
        raise ValueError("Missing scaled XP character")
    level = owner["level"]
    base = monster_base_xp(level)
    amount = _rounded(parameter, base)
    return dict(
        db.execute(
            "INSERT INTO achievement_scaled_xp_receipts "
            "(character_id,achievement_id,cycle_key,reward_key,policy_version,native_parameter,"
            "real_level,native_base_xp,final_amount,payload) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *",
            (*key, POLICY, parameter, level, base, amount, Jsonb(payload)),
        ).fetchone()
    )


def amount(db, character, reward, entitlement):
    """Read frozen XP only; grants cannot create or recompute earned receipts."""
    if db.info.transaction_status != TransactionStatus.INTRANS:
        raise ValueError("Scaled XP delivery requires an owned transaction")
    parameter = _payload(reward)
    if type(entitlement) is not dict or not _same(entitlement.get("payload"), reward):
        raise ValueError("Scaled XP requires its exact durable entitlement")
    key = _key(
        character["id"],
        entitlement.get("achievement_id"),
        entitlement.get("cycle_key"),
        entitlement.get("reward_key"),
        reward,
    )
    owner = db.execute(
        "SELECT id FROM characters WHERE id=%s AND account_id=%s "
        "AND deleted_at IS NULL FOR UPDATE",
        (character["id"], character["account_id"]),
    ).fetchone()
    if owner is None:
        raise ValueError("Scaled XP delivery requires the owned character")
    outbox = db.execute(
        "SELECT payload,delivered_at FROM character_achievement_reward_outbox "
        "WHERE character_id=%s AND achievement_id=%s AND cycle_key=%s AND reward_key=%s FOR UPDATE",
        key,
    ).fetchone()
    frozen = db.execute(
        "SELECT * FROM achievement_scaled_xp_receipts "
        "WHERE character_id=%s AND achievement_id=%s AND cycle_key=%s AND reward_key=%s",
        key,
    ).fetchone()
    if (
        outbox is None
        or not _same(outbox["payload"], reward)
        or frozen is None
        or not _same(frozen["payload"], reward)
        or frozen["native_parameter"] != parameter
        or frozen["policy_version"] != POLICY
    ):
        raise ValueError("Missing frozen scaled XP reservation")
    if outbox["delivered_at"] is not None:
        return None
    return frozen["final_amount"]
