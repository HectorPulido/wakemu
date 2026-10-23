"""Completion-frozen canonical XP rates, independent of native base previews."""
from wakfu_server.reward_rates import MAX_REWARD_RATE_BP, REWARD_RATE_SCALE
from .environmental_runtime import integer


AUTHORITY = "wakemu.environmental-earned-canonical-xp-rate.v1"


def scaled(base, rate):
    integer(base, "environmental base XP", minimum=1)
    integer(rate, "environmental XP rate")
    if rate > MAX_REWARD_RATE_BP:
        raise ValueError("Environmental XP rate exceeds canonical limits")
    return integer(base * rate // REWARD_RATE_SCALE, "environmental earned XP")


def freeze(db, entitlement_id):
    """Called once in the earned entitlement transaction, before delivery."""
    components = db.execute(
        "SELECT * FROM environmental_reward_components WHERE entitlement_id=%s "
        "AND kind='xp' ORDER BY ordinal",
        (entitlement_id,),
    ).fetchall()
    if not components:
        return
    owner = db.execute(
        "SELECT * FROM environmental_reward_entitlements WHERE entitlement_id=%s",
        (entitlement_id,),
    ).fetchone()
    policy = db.execute(
        "SELECT v.version,v.xp_rate_bp FROM combat_reward_policy_active a "
        "JOIN combat_reward_policy_versions v USING(version) "
        "WHERE a.singleton FOR SHARE OF a,v"
    ).fetchone()
    if owner is None or policy is None:
        raise ValueError(
            "Environmental XP requires its earned owner and canonical rate"
        )
    for component in components:
        amount = scaled(component["quantity"], policy["xp_rate_bp"])
        db.execute(
            "INSERT INTO environmental_entitlement_xp_rates "
            "(entitlement_id,component_ordinal,account_id,character_id,earned_at_ms,"
            "policy_version,xp_rate_bp,base_xp,awarded_xp,authority) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                entitlement_id,
                component["ordinal"],
                owner["account_id"],
                owner["character_id"],
                owner["earned_at_ms"],
                policy["version"],
                policy["xp_rate_bp"],
                component["quantity"],
                amount,
                AUTHORITY,
            ),
        )


def award(db, store, character, component):
    """Grant frozen signed64 XP once; caller owns claim receipt/rollback."""
    row = db.execute(
        "SELECT * FROM environmental_entitlement_xp_rates "
        "WHERE entitlement_id=%s AND component_ordinal=%s",
        (component["entitlement_id"], component["ordinal"]),
    ).fetchone()
    amount = component["quantity"]
    if row is not None:
        if (
            row["account_id"],
            row["character_id"],
            row["base_xp"],
            row["authority"],
        ) != (character["account_id"], character["id"], amount, AUTHORITY) or row[
            "awarded_xp"
        ] != scaled(
            amount, row["xp_rate_bp"]
        ):
            raise ValueError("Frozen environmental XP changed owner or source")
        amount = row["awarded_xp"]
    # Pre-migration entitlements retain their already-frozen original base;
    # never retrofit a current policy onto a historical pending reward.
    if amount:
        from wakfu_server.achievements.rewards import _xp

        return _xp(db, store, character, amount)
    return []
