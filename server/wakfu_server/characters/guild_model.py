"""Project authoritative guild snapshots onto the installed native model.

Identity interpretation and synchronization factors are explicit policy. This
adapter must not guess missing required fields or silently serialize stale XP.
"""
import math


def _primary_projection_policy(policy):
    """Validate the explicit Wakemu identity-only projection, not native caps."""
    primary = policy.get("primary_identity_only", False)
    if type(primary) is not bool:
        raise ValueError("Invalid guild primary capability policy")
    if not primary:
        return
    if policy.get("owner_id_semantics") != "account":
        raise ValueError("Primary guild members require their real account owner")
    economy = policy.get("economy")
    if not isinstance(economy, dict) or any(
        economy.get(name) is not False
        for name in ("treasury_enabled", "progression_enabled", "bonuses_enabled")
    ):
        raise ValueError("Primary guild projection requires disabled economy")
    for name in (
        "weekly_points_limit",
        "earned_points_limit",
        "last_earning_point_week",
    ):
        if type(policy.get(name)) is not int or policy[name] != 0:
            raise ValueError("Primary guild projection requires explicit zero counters")
    factor = policy.get("moderation_bonus_learning_factor")
    if type(factor) not in (int, float) or factor != 0:
        raise ValueError("Primary guild projection requires a neutral learning factor")


def _byte(value, name):
    if type(value) is not int or not 0 <= value <= 255:
        raise ValueError("Invalid guild member " + name)
    return bytes((value,))


def point_limits(policy, guild, *, economy_record=None, now=None):
    """Unverified native counters must be supplied explicitly before enabling."""
    _primary_projection_policy(policy)
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
        from wakfu_server.guild_weekly_cap import effective_cap

        guild["weekly_points_limit"] = effective_cap(economy, guild, economy_record)
        from datetime import timedelta, timezone, date

        if not isinstance(economy_record, dict) or now is None:
            raise ValueError(
                "Guild progression projection requires actual stored week authority"
            )
        today = now.astimezone(timezone.utc).date()
        week = (today - timedelta(days=today.weekday())).isoformat()
        earned_week = economy_record.get("week")
        guild["earned_points_limit"] = (
            guild["weekly_points"] if earned_week == week else 0
        )
        guild["last_earning_point_week"] = (
            date.fromisoformat(earned_week).isocalendar().week if earned_week else 0
        )


def native_model(snapshot):
    if snapshot is None:
        return None
    policy = snapshot["policy"]
    _primary_projection_policy(policy)
    semantics = policy.get("owner_id_semantics")
    if semantics not in ("account", "character"):
        raise ValueError("Guild owner identity semantics have not been configured")
    guild = snapshot["guild"]
    members = []
    for row in snapshot["members"]:
        if policy.get("primary_identity_only") is True and any(
            type(row.get(name)) is not int or row[name] <= 0
            for name in ("account_id", "character_id")
        ):
            raise ValueError("Primary guild member requires actual owner identities")
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
    _primary_projection_policy(snapshot["policy"])
    factor = snapshot["policy"].get("moderation_bonus_learning_factor")
    if type(factor) not in (int, float) or not math.isfinite(factor) or factor < 0:
        raise ValueError("Guild moderation learning factor has not been configured")
    return float(factor)
