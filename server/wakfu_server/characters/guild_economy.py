"""Opt-in guild economy authority, independent of unverified native packets.

Every mutation locks the selected session/character, then guild, then wallet.
Policies are deployment rules, not assertions about official Wakfu rules.
No client dispatcher may call accrue_points with client-supplied rewards.
"""
from datetime import timezone, timedelta
import math

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
    if policy.get("permission_model") == "native_guild_storage_v1" and permission in (
        "treasury_deposit",
        "treasury_withdraw",
    ):
        from .guild_storage_policy import treasury_permission

        if row is None or not treasury_permission(row["permissions"], permission):
            raise ValueError("Guild economy permission denied: " + permission)
        return row
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
        from wakfu_server.simple_item_actions import _idle

        _idle(db, character_id, store.now())
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
        return accrue_points_in_transaction(
            db, store, guild_id, character_id, event_key=key, source=source
        )


def accrue_points_in_transaction(
    db, store, guild_id, character_id, *, event_key, source
):
    """Trusted existing-transaction variant; amounts remain policy-owned."""
    _integer(guild_id, "identity", 1)
    _integer(character_id, "character identity", 1)
    key = _key(event_key)
    if not isinstance(source, str) or not 1 <= len(source) <= 200:
        raise ValueError("Invalid guild reward source")
    request = {"guild_id": guild_id, "character_id": character_id, "source": source}
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
    if policy.get("bonus_catalog_authority") == "native_guild_progression_v1":
        from .guild_progression import settle_due

        settle_due(db, store, guild, policy)
        guild = _guild(db, guild_id)
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
    reward = _integer(policy.get("point_sources", {}).get(source), "source reward", 1)
    from wakfu_server.guild_weekly_cap import effective_cap

    state = _state(db, guild_id)
    cap = effective_cap(policy, guild, state)
    now = store.now().astimezone(timezone.utc)
    week = (now.date() - timedelta(days=now.weekday())).isoformat()
    if policy.get("bonus_catalog_authority") == "native_guild_progression_v1":
        from .guild_progression import point_reward

        reward = point_reward(reward, state)
    earned = guild["weekly_points"] if state.get("week") == week else 0
    earned = _integer(earned, "weekly earned")
    awarded = min(reward, max(0, cap - earned))
    points = _integer(guild["current_points"] + awarded, "points", maximum=2**31 - 1)
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
        native_progression = (
            policy.get("bonus_catalog_authority") == "native_guild_progression_v1"
        )
        if native_progression:
            from .guild_progression import settle_due

            settle_due(db, store, guild, policy)
            guild = _guild(db, guild_id)
        _member(
            db,
            guild_id,
            character_id,
            policy,
            "bonus_activate" if activate else "bonus_learn",
        )
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
        manual = bonus.get("activation_mode") == "manual"
        if manual:
            duration = _integer(
                bonus.get("effect", {}).get("duration_ms"), "temporary duration", 1
            )
            cycle = _integer(
                state.get("bonus_cycles", {}).get(
                    str(bonus_id), (record or {}).get("cycle", 0)
                ),
                "temporary cycle",
            )
            if record and not activate and record.get("active") is True:
                activation = _integer(
                    record.get("activated_at_ms"), "temporary activation", 1
                )
                if activation + duration <= now_ms:
                    cycle += 1
            from hashlib import sha256

            key = "timed:" + sha256((key + ":cycle:" + str(cycle)).encode()).hexdigest()
        previous = _receipt(db, character_id, key, request)
        if previous is not None:
            return previous
        if activate:
            if not record or record["learned_at_ms"] > now_ms:
                raise ValueError("Guild bonus has not finished learning")
            if record.get("active"):
                raise ValueError("Guild bonus is already active")
            effect = bonus.get("effect", {})
            _apply_effect(db, guild, effect, store=store, account_id=account_id)
            record = dict(record, active=True, activated_at_ms=now_ms)
            if manual:
                record["expires_at_ms"] = now_ms + duration
            bonuses[str(bonus_id)] = record
            state["bonuses"] = bonuses
            result = dict(request, bonus=record)
            _save(db, guild_id, state, "bonus_activated", result)
            return _finish(db, character_id, key, request, result)
        if record is not None:
            if not (
                manual
                and record.get("active") is True
                and record["activated_at_ms"] + duration <= now_ms
            ):
                raise ValueError("Guild bonus was already purchased")
        if native_progression:
            minimum = _integer(
                bonus.get("minimum_guild_level"), "bonus minimum guild level", 0, 10
            )
            if guild["level"] < minimum:
                raise ValueError("Guild bonus requires a higher guild level")
            effect = bonus.get("effect", {})
            if (
                effect.get("kind") == "unlock_level"
                and effect.get("value") != guild["level"] + 1
            ):
                raise ValueError("Guild level bonus must unlock the next level")
            limit = _integer(
                state.get(
                    "maximum_simultaneous_learning",
                    policy["maximum_simultaneous_learning"],
                ),
                "simultaneous learning",
                1,
                2,
            )
            if (
                sum(
                    row.get("active") is not True and row["learned_at_ms"] > now_ms
                    for row in bonuses.values()
                )
                >= limit
            ):
                raise ValueError("Guild maximum simultaneous learning reached")
            factor = state.get(
                "learning_duration_factor", policy["learning_duration_factor"]
            )
            if type(factor) not in (float, int) or factor not in (1.0, 0.9):
                raise ValueError("Unqualified native guild learning duration factor")
            # Original fhU.a multiplies TT seconds then GS.g rounds up.
            learning_ms = math.ceil(learning_ms / 1000 * factor) * 1000
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
        if bonus.get("effect", {}).get("kind") == "unlock_haven_world":
            record["purchased_by_account_id"] = account_id
        if manual:
            record.update(activation_mode="manual", cycle=cycle)
        bonuses[str(bonus_id)] = record
        state.update(bonuses=bonuses)
        result = dict(request, points=points, bonus=record)
        _save(db, guild_id, state, "bonus_purchased", result)
        if native_progression and learning_ms == 0:
            # Zero-delay native effects and their points debit share one commit.
            settle_due(db, store, guild, policy)
            result["bonus"] = _state(db, guild_id)["bonuses"][str(bonus_id)]
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


def _apply_effect(db, guild, effect, *, store=None, account_id=None):
    """Only explicitly configured permanent noncombat effects are supported."""
    kind = effect.get("kind")
    if kind == "member_effect":
        from wakfu_server.guild_member_effects import effects

        reference = _integer(
            effect.get("reference"), "member effect reference", 1, 2**31 - 1
        )
        from wakfu_server.guild_progression import catalog

        native = [
            row
            for row in catalog()["bonuses"]
            if row["effect_type"] == "MEMBER_EFFECT"
            and row["effect_parameters"]["smu"] == reference
        ]
        if str(reference) not in effects() or not any(
            effect.get("duration_ms")
            == (row["effect_duration_ms"] if row["has_effect_duration"] else -1)
            for row in native
        ):
            raise ValueError("Unqualified guild member effect duration")
        return  # Current membership projection owns the actual native benefit.
    value = _integer(
        effect.get("value"),
        "bonus effect value",
        0 if kind == "unlock_compartment" else 1,
        2**31 - 1,
    )
    if effect.get("duration_ms") != -1:
        raise NotImplementedError("Temporary guild effects need expiry integration")
    if kind == "criterion_bonus":
        return  # The durable active bonus identity is the native effect.
    if kind == "unlock_haven_world":
        from wakfu_server.guild_progression import catalog
        from wakfu_server.guild_haven_world import provision_unlocked_world

        if (
            store is None
            or type(account_id) is not int
            or account_id <= 0
            or not any(
                row["id"] == value and row["effect_type"] == "UNLOCK_HAVEN_WORLD"
                for row in catalog()["bonuses"]
            )
        ):
            raise ValueError("Missing native Haven World purchase authority")
        provision_unlocked_world(db, store, account_id, guild["id"])
        return
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
        _integer(value, "native compartment", 0, 3)
        compartments = list(guild["unlocked_compartments"])
        if value in compartments:
            raise ValueError("Guild compartment already unlocked")
        db.execute(
            "UPDATE guilds SET unlocked_compartments=%s WHERE id=%s",
            (Jsonb(compartments + [value]), guild["id"]),
        )
    else:
        raise NotImplementedError("Guild bonus effect requires a verified backend")


def economy_record(db, guild_id):
    """Pure stored authority for hydration and snapshot publication."""
    row = db.execute(
        "SELECT record FROM guild_service_state WHERE guild_id=%s AND service='economy'",
        (guild_id,),
    ).fetchone()
    return dict(row["record"]) if row else {}


def bonus_snapshot(db, guild_id):
    return economy_record(db, guild_id).get("bonuses", {})
