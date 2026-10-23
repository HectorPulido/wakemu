"""Original guild bonus descriptors and permanent learning transitions.

Reward producers are separately configured Wakemu policy. Catalog costs, level
availability, durations and supported effect operands are original client data.
No member/combat bonus is silently replaced by a metadata-only unlock.
"""
from functools import lru_cache
import json
from pathlib import Path


@lru_cache(maxsize=1)
def catalog():
    source = json.loads(
        Path(__file__).with_name("native_guild_progression.json").read_text()
    )
    rows = source.get("bonuses")
    if (
        source.get("schema_version") != 1
        or not isinstance(rows, list)
        or len(rows) != len({row["id"] for row in rows})
        or sorted(row["level"] for row in source["levels"]) != list(range(11))
    ):
        raise ValueError("Incomplete native guild progression catalog")
    return source


def supported_bonuses():
    """Return effects with qualified durable transitions and member projections."""
    result = {}
    for native in catalog()["bonuses"]:
        kind, params = native["effect_type"], native["effect_parameters"]
        if kind == "UNLOCK_LEVEL":
            effect = dict(
                kind="unlock_level", value=int(params["smx"].removeprefix("LEVEL_"))
            )
        elif kind == "STORAGE_COMPARTMENT":
            effect = dict(
                kind="unlock_compartment",
                value=int(params["smy"].removeprefix("GUILD_")) - 1,
            )
        elif kind == "INCREASE_MEMBERS_SIZE":
            effect = dict(kind="member_capacity", value=params["smt"])
        elif kind == "REDUCE_LEARNING_DURATION":
            effect = dict(
                kind="learning_duration_factor",
                value=catalog()["defaults"]["upgraded_learning_duration_factor"],
            )
        elif kind == "INCREASE_MAX_AUTHORIZED_EVOLUTION":
            effect = dict(
                kind="maximum_simultaneous_learning",
                value=catalog()["defaults"]["upgraded_maximum_simultaneous_learning"],
            )
        elif kind == "SET_POINTS_EARNED_FACTOR":
            effect = dict(kind="points_earned_factor", value=params["smv"])
        elif kind == "SET_WEEKLY_POINTS_LIMIT":
            effect = dict(kind="weekly_point_limit", value=params["smw"])
        elif kind == "UNLOCK_HAVEN_WORLD":
            effect = dict(kind="unlock_haven_world", value=native["id"])
        else:
            from .guild_bonus_authority import native_descriptor

            effect = native_descriptor(native)
            if effect is None:
                from wakfu_server.guild_member_effects import qualified_descriptor

                descriptor = qualified_descriptor(native, include_temporary=True)
                if descriptor is not None:
                    if native["has_effect_duration"]:
                        descriptor["activation_mode"] = "manual"
                        # Wakemu renewal policy reuses the native paid learning cycle.
                        descriptor["renewal_mode"] = "paid_relearn"
                    result[str(native["id"])] = descriptor
                continue
        effect["duration_ms"] = -1
        result[str(native["id"])] = dict(
            cost=native["cost"],
            learning_duration_ms=native["learning_duration_ms"],
            minimum_guild_level=native["minimum_guild_level"],
            effect=effect,
            prerequisites=[],
            native_category=native["category"],
        )
    return result


def progression_policy(base, *, enabled=False, point_sources=None):
    """Compose native progression with reviewed server-only reward policies.

    Empty producers remain empty. Calling this builder never awards points or
    opens compartments, and preserves independent management/treasury policy.
    """
    from .guild_native_validators import permission_bits

    if type(enabled) is not bool or not isinstance(base, dict):
        raise ValueError("Invalid guild progression policy")
    sources = (
        {
            "native_achievement:" + key: row["rewards"][0]["ckl"][0]
            for key, row in catalog()["point_quests"].items()
        }
        if point_sources is None
        else dict(point_sources)
    )
    if any(
        not isinstance(name, str) or type(value) is not int or value <= 0
        for name, value in sources.items()
    ):
        raise ValueError("Guild point sources require explicit positive server rewards")
    economy = dict(base.get("economy", {}))
    bits = dict(economy.get("permission_bits", {}))
    bits.update(
        bonus_learn=permission_bits()["BUY_BONUS"],
        bonus_activate=permission_bits()["BUY_BONUS"],
    )
    economy.update(
        progression_enabled=enabled,
        bonuses_enabled=enabled,
        point_sources=sources,
        weekly_point_cap=catalog()["defaults"]["weekly_point_cap"],
        permission_bits=bits,
        bonus_catalog=supported_bonuses(),
        bonus_catalog_authority="native_guild_progression_v1",
        maximum_simultaneous_learning=catalog()["defaults"][
            "maximum_simultaneous_learning"
        ],
        point_source_origin="native_aJP_type12_guild_quests",
        positive_point_rounding="wakemu_floor_rational_no_fractional_carry",
        learning_duration_factor=catalog()["defaults"]["learning_duration_factor"],
    )
    allowed = list(
        dict.fromkeys((*base.get("native_request_opcodes", ()), 15613, 14447))
    )
    return dict(
        base,
        primary_identity_only=False,
        native_request_opcodes=allowed,
        moderation_bonus_learning_factor=1.0,
        economy=economy,
    )


def settle_due(db, store, guild, policy):
    """Complete due permanent bonuses under the caller's existing guild lock.

    This belongs only to owned mutation/periodic boundaries, never character
    hydration or an AI read-only transaction. Every accepted effect applies
    exactly once and emits the normal post-commit guild event.
    """
    from . import guild_economy as economy

    if policy.get("bonuses_enabled") is not True:
        return ()
    state = economy._state(db, guild["id"])
    bonuses = dict(state.get("bonuses", {}))
    now = int(store.now().timestamp() * 1000)
    expired = []
    cycles = dict(state.get("bonus_cycles", {}))
    for key, row in tuple(bonuses.items()):
        descriptor = policy.get("bonus_catalog", {}).get(key, {})
        if (
            descriptor.get("activation_mode") == "manual"
            and row.get("active") is True
            and row["activated_at_ms"] + descriptor["effect"]["duration_ms"] <= now
        ):
            cycles[key] = economy._integer(row.get("cycle", 0), "temporary cycle") + 1
            del bonuses[key]
            expired.append(int(key))
    due = sorted(
        (row["learned_at_ms"], int(key))
        for key, row in bonuses.items()
        if row.get("active") is not True and row["learned_at_ms"] <= now
    )
    completed = []
    for learned_at, identity in due:
        descriptor = policy.get("bonus_catalog", {}).get(str(identity))
        if not isinstance(descriptor, dict):
            raise ValueError("Pending guild bonus has no qualified descriptor")
        effect = descriptor["effect"]
        if descriptor.get("activation_mode") == "manual":
            continue
        if effect["kind"] in (
            "learning_duration_factor",
            "maximum_simultaneous_learning",
            "points_earned_factor",
        ):
            state[effect["kind"]] = effect["value"]
        elif effect["kind"] == "weekly_point_limit":
            state["native_weekly_point_cap"] = economy._integer(
                effect["value"], "native weekly total limit", 1, 2**31 - 1
            )
        else:
            economy._apply_effect(
                db,
                guild,
                effect,
                store=store,
                account_id=bonuses[str(identity)].get("purchased_by_account_id"),
            )
            # Later due transitions see the actual updated aggregate.
            guild = economy._guild(db, guild["id"])
        bonuses[str(identity)] = dict(
            bonuses[str(identity)], active=True, activated_at_ms=learned_at
        )
        completed.append(identity)
    if completed or expired:
        state["bonuses"] = bonuses
        state["bonus_cycles"] = cycles
        economy._save(
            db,
            guild["id"],
            state,
            "bonuses_expired" if expired else "bonuses_learned",
            dict(guild_id=guild["id"], bonus_ids=completed, expired_bonus_ids=expired),
        )
    return tuple(completed + expired)


def tick(store, *, limit=16):
    """Bounded server-owned clock producer; normal outbox handles publication."""
    from . import guild_economy as economy

    if type(limit) is not int or not 1 <= limit <= 64:
        raise ValueError("Invalid guild progression batch limit")
    with store.connection() as db:
        row = db.execute(
            "SELECT value FROM settings WHERE name='guild_policy'"
        ).fetchone()
        policy = row["value"] if row else {}
        rules = policy.get("economy", {})
        if (
            policy.get("enabled") is not True
            or rules.get("bonuses_enabled") is not True
            or rules.get("bonus_catalog_authority") != "native_guild_progression_v1"
        ):
            return ()
        now = int(store.now().timestamp() * 1000)
        guilds = db.execute(
            "SELECT g.* FROM guilds g JOIN guild_service_state s ON s.guild_id=g.id "
            "AND s.service='economy' WHERE g.dissolved_at IS NULL AND (EXISTS("
            "SELECT 1 FROM jsonb_each(COALESCE(s.record->'bonuses','{}'::jsonb)) b "
            "WHERE COALESCE((b.value->>'active')::boolean,false)=false AND COALESCE(b.value->>'activation_mode','automatic')<>'manual' "
            "AND (b.value->>'learned_at_ms')::bigint<=%s) OR EXISTS("
            "SELECT 1 FROM jsonb_each(COALESCE(s.record->'bonuses','{}'::jsonb)) b "
            "WHERE (b.value->>'active')::boolean=true "
            "AND b.value->>'activation_mode'='manual' "
            "AND (b.value->>'expires_at_ms')::bigint<=%s) "
            ") ORDER BY g.id LIMIT %s FOR UPDATE OF g SKIP LOCKED",
            (now, now, limit),
        ).fetchall()
        return tuple(
            (guild["id"], settle_due(db, store, guild, rules)) for guild in guilds
        )


def grant_achievement_reward(db, store, character, reward, entitlement):
    """Grant original type12 only from a durable, completed native quest cycle.

    The outbox carries the guild captured at completion. A different guild can
    never redeem that old entitlement. Event identity is derived from the
    original repeat period and completion date, not a caller-selected nonce.
    """
    from . import guild_economy as economy
    from wakfu_server.achievements.rewards import RewardCapacity

    if not isinstance(entitlement, dict):
        raise ValueError("Guild achievement reward requires a durable entitlement")
    identity = entitlement.get("achievement_id")
    native = catalog()["point_quests"].get(str(identity))
    if native is None:
        raise ValueError("Missing original guild achievement reward authority")
    wanted = {key: reward.get(key) for key in ("d", "aeV", "ckl")}
    if wanted not in native["rewards"] or str(reward["d"]) != entitlement.get(
        "reward_key"
    ):
        raise ValueError("Guild reward differs from original achievement payload")
    stored = db.execute(
        "SELECT payload,delivered_at FROM character_achievement_reward_outbox "
        "WHERE character_id=%s AND achievement_id=%s AND cycle_key=%s AND reward_key=%s FOR UPDATE",
        (
            character["id"],
            identity,
            entitlement.get("cycle_key"),
            entitlement.get("reward_key"),
        ),
    ).fetchone()
    if (
        stored is None
        or stored["payload"] != reward
        or stored["delivered_at"] is not None
    ):
        raise ValueError("Missing pending guild achievement entitlement")
    completed = reward.get("_guild_completion_date_ms")
    anchor, period = native["native"]["efu"], native["native"]["efv"] * 1000
    if type(completed) is not int or completed < anchor or period <= 0:
        raise ValueError("Invalid native guild quest completion cycle")
    cycle = (completed - anchor) // period
    guild_id = reward.get("_guild_id")
    if type(guild_id) is not int or guild_id <= 0:
        raise ValueError("Guild reward requires its earned guild identity")
    if entitlement.get("cycle_key") != "guild-daily:" + str(cycle):
        raise ValueError("Guild reward differs from its native daily cycle")
    earned = db.execute(
        "SELECT earned_guild_id,completed_at_ms FROM character_guild_daily_quests "
        "WHERE character_id=%s AND definition_id=%s AND cycle_index=%s",
        (character["id"], identity, cycle),
    ).fetchone()
    if (
        earned is None
        or earned["earned_guild_id"] != guild_id
        or earned["completed_at_ms"] != completed
    ):
        raise RewardCapacity(
            "Earned guild quest awaits its exact durable completion cycle"
        )
    member = db.execute(
        "SELECT guild_id FROM guild_members WHERE character_id=%s", (character["id"],)
    ).fetchone()
    if member is None or member["guild_id"] != guild_id:
        # Retain the earned entitlement instead of paying another guild or
        # failing character selection. The ordinary pending outbox retries it.
        raise RewardCapacity(
            "Earned guild achievement is awaiting its original guild membership"
        )
    policy = economy._policy(db, "progression_enabled")
    source = "native_achievement:" + str(identity)
    if policy.get("point_sources", {}).get(source) != reward["ckl"][0]:
        raise ValueError("Guild quest reward amount differs from original source")
    return economy.accrue_points_in_transaction(
        db,
        store,
        guild_id,
        character["id"],
        event_key="native-guild-quest:"
        + str(character["id"])
        + ":"
        + str(identity)
        + ":"
        + str((completed - anchor) // period),
        source=source,
    )


def point_reward(base, state):
    """Explicit Wakemu floor of a positive original guild reward, no carry.

    The native base amount and factor are data; integer rounding was not
    recovered from an original server. Exact rational arithmetic avoids binary
    floating artifacts without inventing fractional account balances.
    """
    from fractions import Fraction

    if type(base) is not int or not 0 < base < 2**31:
        raise ValueError("Invalid original guild point amount")
    factor = state.get("points_earned_factor", 1)
    native = [
        row["effect_parameters"]["smv"]
        for row in catalog()["bonuses"]
        if row["effect_type"] == "SET_POINTS_EARNED_FACTOR"
    ]
    if type(factor) not in (int, float) or factor not in (1, *native):
        raise ValueError("Unqualified native guild point factor")
    ratio = Fraction(str(factor))
    reward = base * ratio.numerator // ratio.denominator
    if not 0 < reward < 2**31:
        raise ValueError("Guild point reward exceeds native bounds")
    return reward
