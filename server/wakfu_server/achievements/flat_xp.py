"""Freeze the global displayed XP rate when a fixed mission reward is earned."""
from wakfu_server.reward_rates import MAX_REWARD_RATE_BP, REWARD_RATE_SCALE


def scaled(base, rate):
    if type(base) is not int or not 0 < base < 2**31:
        raise ValueError("Invalid fixed achievement XP")
    if type(rate) is not int or not 0 <= rate <= MAX_REWARD_RATE_BP:
        raise ValueError("Invalid achievement XP rate")
    amount = base * rate // REWARD_RATE_SCALE
    if amount >= 2**63:
        raise ValueError("Achievement XP exceeds signed64 storage")
    return amount


def reserve(db, character_id, achievement_id, cycle_key, reward_key, reward):
    """The enclosing transaction locks the owner and owns the outbox row."""
    from .rewards import validate

    kind, params = validate(reward)
    if kind != 6 or str(reward.get("d")) != reward_key:
        raise ValueError("Invalid fixed achievement XP entitlement")
    key = (character_id, achievement_id, cycle_key, reward_key)
    existing = db.execute(
        "SELECT base_xp FROM achievement_flat_xp_rates WHERE character_id=%s "
        "AND achievement_id=%s AND cycle_key=%s AND reward_key=%s",
        key,
    ).fetchone()
    if existing is not None:
        if existing["base_xp"] != params[0]:
            raise ValueError("Fixed achievement XP identity changed")
        return
    policy = db.execute(
        "SELECT v.version,v.xp_rate_bp FROM combat_reward_policy_active a "
        "JOIN combat_reward_policy_versions v USING(version) WHERE a.singleton FOR SHARE OF a,v"
    ).fetchone()
    if policy is None:
        raise ValueError("Missing achievement XP rate")
    db.execute(
        "INSERT INTO achievement_flat_xp_rates "
        "(character_id,achievement_id,cycle_key,reward_key,policy_version,xp_rate_bp,base_xp,awarded_xp) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
        (
            *key,
            policy["version"],
            policy["xp_rate_bp"],
            params[0],
            scaled(params[0], policy["xp_rate_bp"]),
        ),
    )


def amount(db, character, reward, entitlement):
    """Read the frozen amount; pre-existing outbox entries retain their old value."""
    base = reward["ckl"][0]
    if entitlement is None:
        return base
    if (
        not isinstance(entitlement, dict)
        or entitlement.get("payload") != reward
        or entitlement.get("reward_key") != str(reward["d"])
    ):
        raise ValueError("Invalid fixed achievement XP entitlement")
    row = db.execute(
        "SELECT base_xp, xp_rate_bp, awarded_xp FROM achievement_flat_xp_rates "
        "WHERE character_id=%s AND achievement_id=%s AND cycle_key=%s AND reward_key=%s",
        (
            character["id"],
            entitlement["achievement_id"],
            entitlement["cycle_key"],
            entitlement["reward_key"],
        ),
    ).fetchone()
    if row is None:  # Legacy outstanding rewards were earned under the old policy.
        return base
    if row["base_xp"] != base or row["awarded_xp"] != scaled(base, row["xp_rate_bp"]):
        raise ValueError("Fixed achievement XP receipt mismatch")
    return row["awarded_xp"]
