"""Project authoritative guild snapshots onto the installed native model.

Identity interpretation and synchronization factors are explicit policy. This
adapter must not guess missing required fields or silently serialize stale XP.
"""
import math


def _byte(value, name):
    if type(value) is not int or not 0 <= value <= 255:
        raise ValueError("Invalid guild member " + name)
    return bytes((value,))


def point_limits(policy, guild):
    """Unverified native counters must be supplied explicitly before enabling."""
    for field in (
        "weekly_points_limit",
        "earned_points_limit",
        "last_earning_point_week",
    ):
        if policy.get("native_sync_enabled") is True and field not in policy:
            raise ValueError("Guild native point field is not configured: " + field)
        value = policy.get(field, 0)
        if type(value) is not int or not 0 <= value < 2**31:
            raise ValueError("Invalid guild native point field: " + field)
        guild[field] = value
    economy = policy.get("economy", {})
    if economy.get("progression_enabled") is True:
        cap = economy.get("weekly_point_cap")
        if (
            type(cap) is not int
            or not 1 <= cap + guild["weekly_capacity_bonus"] < 2**31
        ):
            raise ValueError("Invalid guild weekly point cap")
        guild["weekly_points_limit"] = cap + guild["weekly_capacity_bonus"]


def native_model(snapshot):
    if snapshot is None:
        return None
    policy = snapshot["policy"]
    semantics = policy.get("owner_id_semantics")
    if semantics not in ("account", "character"):
        raise ValueError("Guild owner identity semantics have not been configured")
    guild = snapshot["guild"]
    members = []
    for row in snapshot["members"]:
        members.append(
            {
                "id": row["character_id"],
                "ownerId": row["account_id"]
                if semantics == "account"
                else row["character_id"],
                "guildPoints": row["points"],
                "rank": row["rank_id"],
                "xp": row["xp"],
                "isConnected": row["connected"],
                "smiley": _byte(row.get("smiley", 0), "smiley"),
                "sex": _byte(int(row["sex"]), "sex"),
                "breedId": row["breed"],
                "nationId": row.get("nation_id", 0),
                "name": row["name"],
                "saveDate": row["save_date"],
                "serializedLanguages": _byte(row["language_mask"], "language mask"),
                "accountCommunityId": _byte(row["community"], "community"),
            }
        )
    return {
        "guildId": guild["id"],
        "level": guild["level"],
        "blazon": guild["blazon"],
        "name": guild["name"],
        "description": guild["description"],
        "message": guild["message"],
        "currentGuildPoints": guild["current_points"],
        "totalGuildPoints": guild["total_points"],
        "weeklyPointsLimit": guild["weekly_points_limit"],
        "earnedPointsLimit": guild["earned_points_limit"],
        "lastEarningPointWeek": guild["last_earning_point_week"],
        "ranks": [
            dict(
                id=row["id"],
                name=row["name"],
                authorizations=row["permissions"],
                position=row["position"],
            )
            for row in snapshot["ranks"]
        ],
        "members": members,
        "bonuses": [
            dict(
                id=row["bonus_id"],
                activationDate=row["activation_date"],
                buyDate=row["buy_date"],
            )
            for row in snapshot["bonuses"]
        ],
    }


def moderation_factor(snapshot):
    if snapshot is None:
        return 0.0
    factor = snapshot["policy"].get("moderation_bonus_learning_factor")
    if type(factor) not in (int, float) or not math.isfinite(factor) or factor < 0:
        raise ValueError("Guild moderation learning factor has not been configured")
    return float(factor)
