"""Opt-in guild economy authority, independent of unverified native packets.

Every mutation locks the selected session/character, then guild, then wallet.
Policies are deployment rules, not assertions about official Wakfu rules.
No client dispatcher may call accrue_points with client-supplied rewards.
"""
from datetime import timezone, timedelta

from psycopg.types.json import Jsonb

MAX_BALANCE = 2**63 - 1


def _integer(value, name, minimum=0, maximum=MAX_BALANCE):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError("Invalid guild " + name)
    return value


def _key(value):
    if not isinstance(value, str) or not 1 <= len(value) <= 200:
        raise ValueError("Invalid guild operation key")
    return value


def _policy(db, capability):
    row = db.execute("SELECT value FROM settings WHERE name='guild_policy'").fetchone()
    policy = row["value"] if row else {}
    economy = policy.get("economy", {})
    if policy.get("enabled") is not True or economy.get(capability) is not True:
        raise ValueError("Guild economy capability is disabled: " + capability)
    return economy


def _guild(db, guild_id):
    row = db.execute(
        "SELECT * FROM guilds WHERE id=%s AND dissolved_at IS NULL FOR UPDATE",
        (guild_id,),
    ).fetchone()
    if row is None:
        raise ValueError("Guild does not exist")
    return row


def _member(db, guild_id, character_id, policy, permission):
    row = db.execute(
        "SELECT m.*,r.permissions FROM guild_members m JOIN guild_ranks r ON r.id=m.rank_id "
        "AND r.guild_id=m.guild_id WHERE m.guild_id=%s AND m.character_id=%s",
        (guild_id, character_id),
    ).fetchone()
    bit = policy.get("permission_bits", {}).get(permission)
    if (
        row is None
        or type(bit) is not int
        or not 0 <= bit < 63
        or not row["permissions"] & (1 << bit)
    ):
        raise ValueError("Guild economy permission denied: " + permission)
    return row


def _state(db, guild_id):
    db.execute(
        "INSERT INTO guild_service_state(guild_id,service) VALUES(%s,'economy') ON CONFLICT DO NOTHING",
        (guild_id,),
    )
    return dict(
        db.execute(
            "SELECT record FROM guild_service_state WHERE guild_id=%s AND service='economy' FOR UPDATE",
            (guild_id,),
        ).fetchone()["record"]
    )


def _save(db, guild_id, state, kind, result):
    db.execute(
        "UPDATE guild_service_state SET record=%s WHERE guild_id=%s AND service='economy'",
        (Jsonb(state), guild_id),
    )
    revision = db.execute(
        "UPDATE guilds SET revision=revision+1 WHERE id=%s RETURNING revision",
        (guild_id,),
    ).fetchone()["revision"]
    db.execute(
        "INSERT INTO guild_events(guild_id,revision,kind,payload) VALUES(%s,%s,%s,%s)",
        (guild_id, revision, kind, Jsonb(result)),
    )


def _receipt(db, character_id, key, request):
    row = db.execute(
        "SELECT request,result FROM guild_operation_receipts WHERE character_id=%s AND operation_key=%s",
        (character_id, key),
    ).fetchone()
    if row and row["request"] != request:
        raise ValueError("Guild operation key reused with another request")
    return row["result"] if row else None


def _finish(db, character_id, key, request, result):
    db.execute(
        "INSERT INTO guild_operation_receipts(character_id,operation_key,request,result) VALUES(%s,%s,%s,%s)",
        (character_id, key, Jsonb(request), Jsonb(result)),
    )
    return result


def transfer_kamas(
    store,
    account_id,
    generation,
    character_id,
    guild_id,
    amount,
    *,
    withdraw=False,
    operation_key
):
    """Conserve account + treasury balances, including retries and rollback."""
    _integer(amount, "amount", 1)
    _integer(guild_id, "identity", 1)
    if type(withdraw) is not bool:
        raise ValueError("Invalid guild transfer direction")
    key = _key(operation_key)
    request = {
        "operation": "treasury",
        "guild_id": guild_id,
        "amount": amount,
        "withdraw": withdraw,
    }
    with store.connection() as db:
        store.lock_character(db, account_id, generation, character_id)
        _guild(db, guild_id)
        policy = _policy(db, "treasury_enabled")
        _member(
            db,
            guild_id,
            character_id,
            policy,
            "treasury_withdraw" if withdraw else "treasury_deposit",
        )
        previous = _receipt(db, character_id, key, request)
        if previous is not None:
            return previous
        state = _state(db, guild_id)
        treasury = _integer(state.get("kamas", 0), "treasury balance")
        row = db.execute(
            "SELECT kamas FROM account_wallets WHERE account_id=%s FOR UPDATE",
            (account_id,),
        ).fetchone()
        if row is None:
            raise ValueError("Account wallet does not exist")
        wallet = _integer(row["kamas"], "wallet balance")
        change = -amount if withdraw else amount
        new_treasury = _integer(treasury + change, "treasury balance")
        new_wallet = _integer(wallet - change, "wallet balance")
        db.execute(
            "UPDATE account_wallets SET kamas=%s WHERE account_id=%s",
            (new_wallet, account_id),
        )
        state["kamas"] = new_treasury
        result = dict(
            request,
            character_id=character_id,
            account_id=account_id,
            wallet_kamas=new_wallet,
            treasury_kamas=new_treasury,
        )
        _save(db, guild_id, state, "treasury_transfer", result)
        return _finish(db, character_id, key, request, result)


def accrue_points(store, guild_id, character_id, *, event_key, source):
    """Trusted server API. Reward amounts come exclusively from policy.

    UTC Monday weeks are an explicit local policy choice. The cap is shared
    by all members; expelled members cannot contribute using stale events.
    """
    _integer(guild_id, "identity", 1)
    _integer(character_id, "character identity", 1)
    key = _key(event_key)
    if not isinstance(source, str) or not 1 <= len(source) <= 200:
        raise ValueError("Invalid guild reward source")
    request = {"guild_id": guild_id, "character_id": character_id, "source": source}
    with store.connection() as db:
        # Preserve the character-before-guild order of all actor mutations.
        if (
            db.execute(
                "SELECT id FROM characters WHERE id=%s AND deleted_at IS NULL FOR UPDATE",
                (character_id,),
            ).fetchone()
            is None
        ):
            raise ValueError("Guild reward character does not exist")
        guild = _guild(db, guild_id)
        policy = _policy(db, "progression_enabled")
        previous = db.execute(
            "SELECT request,result FROM guild_progression_receipts WHERE guild_id=%s AND event_key=%s",
            (guild_id, key),
        ).fetchone()
        if previous:
            if previous["request"] != request:
                raise ValueError("Guild reward key reused with another event")
            return previous["result"]
        if (
            db.execute(
                "SELECT 1 FROM guild_members WHERE guild_id=%s AND character_id=%s",
                (guild_id, character_id),
            ).fetchone()
            is None
        ):
            raise ValueError("Guild reward character is not a member")
        reward = _integer(
            policy.get("point_sources", {}).get(source), "source reward", 1
        )
        cap = _integer(
            _integer(policy.get("weekly_point_cap"), "weekly cap", 1, 2**31 - 1)
            + guild["weekly_capacity_bonus"],
            "effective weekly cap",
            1,
            2**31 - 1,
        )
        now = store.now().astimezone(timezone.utc)
        week = (now.date() - timedelta(days=now.weekday())).isoformat()
        state = _state(db, guild_id)
        earned = guild["weekly_points"] if state.get("week") == week else 0
        earned = _integer(earned, "weekly earned")
        awarded = min(reward, max(0, cap - earned))
        points = _integer(
            guild["current_points"] + awarded, "points", maximum=2**31 - 1
        )
        total = _integer(
            guild["total_points"] + awarded, "total points", maximum=2**31 - 1
        )
        member = db.execute(
            "SELECT points FROM guild_members WHERE guild_id=%s AND character_id=%s",
            (guild_id, character_id),
        ).fetchone()
        _integer(member["points"] + awarded, "member points", maximum=2**31 - 1)
        state.update(week=week)
        db.execute(
            "UPDATE guilds SET current_points=%s,total_points=%s,weekly_points=%s WHERE id=%s",
            (points, total, earned + awarded, guild_id),
        )
        db.execute(
            "UPDATE guild_members SET points=points+%s WHERE guild_id=%s AND character_id=%s",
            (awarded, guild_id, character_id),
        )
        result = dict(
            request,
            awarded=awarded,
            points=points,
            week=week,
            weekly_earned=earned + awarded,
        )
        _save(db, guild_id, state, "points_earned", result)
        db.execute(
            "INSERT INTO guild_progression_receipts(guild_id,event_key,request,result) VALUES(%s,%s,%s,%s)",
            (guild_id, key, Jsonb(request), Jsonb(result)),
        )
        return result


def transfer_chest_item(*args, **kwargs):
    """Delegate item custody to the shared guild chest transaction engine."""
    from .guild_chest import transfer

    return transfer(*args, **kwargs)


def bonus_operation(
    store,
    account_id,
    generation,
    character_id,
    guild_id,
    bonus_id,
    *,
    activate=False,
    operation_key
):
    """Learn catalog bonuses; activation is unavailable without effect integration.

    A future adapter must use this transaction and must never commit or publish
    independently. Combat/stat effects are intentionally not supplied here.
    """
    _integer(guild_id, "identity", 1)
    _integer(bonus_id, "bonus identity", 1, 2**31 - 1)
    if type(activate) is not bool:
        raise ValueError("Invalid guild bonus operation")
    key = _key(operation_key)
    request = {
        "operation": "bonus",
        "guild_id": guild_id,
        "bonus_id": bonus_id,
        "activate": activate,
    }
    with store.connection() as db:
        store.lock_character(db, account_id, generation, character_id)
        guild = _guild(db, guild_id)
        policy = _policy(db, "bonuses_enabled")
        _member(
            db,
            guild_id,
            character_id,
            policy,
            "bonus_activate" if activate else "bonus_learn",
        )
        previous = _receipt(db, character_id, key, request)
        if previous is not None:
            return previous
        catalog = policy.get("bonus_catalog", {})
        bonus = catalog.get(str(bonus_id))
        if not isinstance(bonus, dict):
            raise ValueError("Guild bonus is not configured")
        cost = _integer(bonus.get("cost"), "bonus cost")
        learning_ms = _integer(
            bonus.get("learning_duration_ms"), "bonus learning duration"
        )
        state = _state(db, guild_id)
        bonuses = dict(state.get("bonuses", {}))
        record = bonuses.get(str(bonus_id))
        now_ms = int(store.now().timestamp() * 1000)
        if activate:
            if not record or record["learned_at_ms"] > now_ms:
                raise ValueError("Guild bonus has not finished learning")
            if record.get("active"):
                raise ValueError("Guild bonus is already active")
            effect = bonus.get("effect", {})
            _apply_effect(db, guild, effect)
            record = dict(record, active=True, activated_at_ms=now_ms)
            bonuses[str(bonus_id)] = record
            state["bonuses"] = bonuses
            result = dict(request, bonus=record)
            _save(db, guild_id, state, "bonus_activated", result)
            return _finish(db, character_id, key, request, result)
        if record is not None:
            raise ValueError("Guild bonus was already purchased")
        prerequisites = bonus.get("prerequisites", [])
        if not isinstance(prerequisites, list):
            raise ValueError("Invalid guild bonus prerequisites")
        for prerequisite in prerequisites:
            prerequisite = _integer(prerequisite, "prerequisite", 1, 2**31 - 1)
            prior = bonuses.get(str(prerequisite))
            if not prior or prior["learned_at_ms"] > now_ms:
                raise ValueError("Guild bonus prerequisite has not been learned")
        points = _integer(guild["current_points"] - cost, "points", maximum=2**31 - 1)
        db.execute(
            "UPDATE guilds SET current_points=%s WHERE id=%s", (points, guild_id)
        )
        record = {
            "purchased_at_ms": now_ms,
            "learned_at_ms": now_ms + learning_ms,
            "active": False,
        }
        bonuses[str(bonus_id)] = record
        state.update(bonuses=bonuses)
        result = dict(request, points=points, bonus=record)
        _save(db, guild_id, state, "bonus_purchased", result)
        return _finish(db, character_id, key, request, result)


def snapshot(store, account_id, generation, character_id, guild_id):
    """Read private economic state only for a current selected guild member."""
    with store.connection() as db:
        store.lock_character(db, account_id, generation, character_id)
        guild = _guild(db, guild_id)
        if (
            db.execute(
                "SELECT 1 FROM guild_members WHERE guild_id=%s AND character_id=%s",
                (guild_id, character_id),
            ).fetchone()
            is None
        ):
            raise ValueError("Guild economy access denied")
        return dict(
            _state(db, guild_id),
            current_points=guild["current_points"],
            total_points=guild["total_points"],
            weekly_points=guild["weekly_points"],
        )


def _apply_effect(db, guild, effect):
    """Only explicitly configured permanent noncombat effects are supported."""
    kind = effect.get("kind")
    value = _integer(effect.get("value"), "bonus effect value", 1, 2**31 - 1)
    if effect.get("duration_ms") != -1:
        raise NotImplementedError("Temporary guild effects need expiry integration")
    if kind == "unlock_level":
        if value != guild["level"] + 1 or value > 10:
            raise ValueError("Guild level bonus must unlock the next level")
        db.execute("UPDATE guilds SET level=%s WHERE id=%s", (value, guild["id"]))
    elif kind in ("member_capacity", "weekly_capacity"):
        column = {
            "member_capacity": "member_capacity_bonus",
            "weekly_capacity": "weekly_capacity_bonus",
        }[kind]
        updated = _integer(guild[column] + value, "capacity", maximum=2**31 - 1)
        db.execute(
            "UPDATE guilds SET " + column + "=%s WHERE id=%s", (updated, guild["id"])
        )
    elif kind == "unlock_compartment":
        compartments = list(guild["unlocked_compartments"])
        if value in compartments:
            raise ValueError("Guild compartment already unlocked")
        db.execute(
            "UPDATE guilds SET unlocked_compartments=%s WHERE id=%s",
            (Jsonb(compartments + [value]), guild["id"]),
        )
    else:
        raise NotImplementedError("Guild bonus effect requires a verified backend")


def bonus_snapshot(db, guild_id):
    row = db.execute(
        "SELECT record FROM guild_service_state WHERE guild_id=%s AND service='economy'",
        (guild_id,),
    ).fetchone()
    return row["record"].get("bonuses", {}) if row else {}
