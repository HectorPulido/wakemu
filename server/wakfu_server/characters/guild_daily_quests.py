"""Original guild daily achievements driven by owned settlement receipts.

Native1389/1390 counters, thresholds, period and rewards are catalog data.
Original localized rules require +/-35 hero/profession levels, exclude kama
crafting, and require a dungeon boss within50 levels for1391. No client event
or caller-selected amount can award guild points through this module.
"""
from copy import deepcopy
from functools import lru_cache
import struct

from wakfu_server.achievements import storage, wire

_VARIABLES = {1389: 293, 1390: 294}
_OBJECTIVES = {1389: 2573, 1390: 2574, 1391: 2575}


def _rules():
    from .guild_progression import catalog

    return catalog()["point_quests"]


def _enabled(db):
    row = db.execute("SELECT value FROM settings WHERE name='guild_policy'").fetchone()
    value = row["value"] if row else {}
    return (
        value.get("enabled") is True
        and value.get("economy", {}).get("progression_enabled") is True
        and value.get("economy", {}).get("point_source_origin")
        == "native_aJP_type12_guild_quests"
    )


def cycle(identity, now_ms):
    rule = _rules().get(str(identity))
    if rule is None or type(now_ms) is not int:
        raise ValueError("Unknown original guild daily quest")
    native = rule["native"]
    if (
        native["efj"] != "IsInGuild()"
        or native["efr"] != 1
        or native["efs"] is not True
        or native["efu"] != 1346457600000
        or native["efv"] != 86400
        or now_ms < native["efu"]
    ):
        raise ValueError("Unqualified native guild daily lifecycle")
    return (now_ms - native["efu"]) // (native["efv"] * 1000)


def _now(db, store=None):
    if store is not None:
        return int(store.now().timestamp() * 1000)
    return db.execute(
        "SELECT (EXTRACT(EPOCH FROM CURRENT_TIMESTAMP)*1000)::bigint AS now_ms"
    ).fetchone()["now_ms"]


def _member(db, character_id):
    row = db.execute(
        "SELECT m.guild_id FROM guild_members m JOIN guilds g ON g.id=m.guild_id "
        "WHERE m.character_id=%s AND g.dissolved_at IS NULL",
        (character_id,),
    ).fetchone()
    return None if row is None else row["guild_id"]


def synchronize(db, character_id, *, now_ms=None):
    """Expire prior native cycles on existing journal/bootstrap boundaries."""
    if not _enabled(db):
        return []
    now_ms = _now(db) if now_ms is None else now_ms
    rows = db.execute(
        "SELECT DISTINCT ON(definition_id) definition_id,cycle_index "
        "FROM character_guild_daily_quests WHERE character_id=%s "
        "ORDER BY definition_id,cycle_index DESC",
        (character_id,),
    ).fetchall()
    expired = [
        row["definition_id"]
        for row in rows
        if row["cycle_index"] < cycle(row["definition_id"], now_ms)
    ]
    if not expired:
        return []
    before = storage.load_locked(db, character_id)
    after = deepcopy(before)
    resets = []
    for identity in expired:
        changed = (
            identity in after["running"]
            or identity in after["completed"]
            or _OBJECTIVES[identity] in after["objectives"]
        )
        after["running"] = [x for x in after["running"] if x != identity]
        after["completed"] = [x for x in after["completed"] if x != identity]
        after["objectives"] = [
            x for x in after["objectives"] if x != _OBJECTIVES[identity]
        ]
        after["completion_dates"].pop(str(identity), None)
        after["tracking"] = [x for x in after["tracking"] if x != identity]
        if identity in _VARIABLES:
            after["variables"][str(_VARIABLES[identity])] = 0
        if changed:
            resets.append((13205, struct.pack(">qi", character_id, identity)))
    if after != before:
        storage.store(db, character_id, after)
    return resets + wire.changes(character_id, before, after, [], [], now_ms)


def synchronize_owned(
    store, account_id, generation, character_id, *, next_boundary_ms=None, now_ms=None
):
    """Publish a daily reset once per native day, with no idle SQL between.

    The session owns the returned next boundary; it must not come from a
    client packet. Failures leave that caller cache unchanged for retry.
    """
    now_ms = int(store.now().timestamp() * 1000) if now_ms is None else now_ms
    if type(now_ms) is not int or now_ms < 0:
        raise ValueError("Invalid guild daily checkpoint clock")
    if next_boundary_ms is not None:
        if type(next_boundary_ms) is not int or next_boundary_ms < 0:
            raise ValueError("Invalid guild daily checkpoint boundary")
        if now_ms < next_boundary_ms:
            return next_boundary_ms, []
    boundaries = []
    for identity in _OBJECTIVES:
        index = cycle(identity, now_ms)
        native = _rules()[str(identity)]["native"]
        boundaries.append(native["efu"] + (index + 1) * native["efv"] * 1000)
    with store.connection() as db:
        store.lock_character(db, account_id, generation, character_id)
        packets = synchronize(db, character_id, now_ms=now_ms)
    return min(boundaries), packets


def activate(store, account_id, generation, character_id, body):
    """Original cnK13397 requests one explicit daily guild achievement."""
    if type(body) is not bytes or len(body) != 4:
        raise ValueError("Invalid native guild quest activation")
    (identity,) = struct.unpack(">i", body)
    if identity not in _OBJECTIVES:
        raise ValueError("Unqualified native guild quest")
    with store.connection() as db:
        store.lock_character(db, account_id, generation, character_id)
        if not _enabled(db):
            raise ValueError("Guild daily quests are unavailable")
        guild_id = _member(db, character_id)
        if guild_id is None:
            raise ValueError("A guild is required to accept this quest")
        now_ms = _now(db, store)
        packets = synchronize(db, character_id, now_ms=now_ms)
        current_cycle = cycle(identity, now_ms)
        prior = db.execute(
            "SELECT 1 FROM character_guild_daily_quests "
            "WHERE character_id=%s AND definition_id=%s AND cycle_index=%s",
            (character_id, identity, current_cycle),
        ).fetchone()
        if prior is not None:
            return dict(applied=False, packets=packets, definition_id=identity)
        before = storage.load_locked(db, character_id)
        if identity in before["completed"]:
            raise ValueError(
                "Existing guild completion lacks its daily cycle authority"
            )
        db.execute(
            "INSERT INTO character_guild_daily_quests(character_id,definition_id,cycle_index,"
            "activation_guild_id,activated_at_ms) VALUES(%s,%s,%s,%s,%s)",
            (character_id, identity, current_cycle, guild_id, now_ms),
        )
        storage.record_event(
            db,
            character_id,
            f"guild-daily-activation:{identity}:{current_cycle}",
            dict(
                kind="native_guild_daily_activation",
                definition_id=identity,
                cycle=current_cycle,
                guild_id=guild_id,
            ),
        )
        after = deepcopy(before)
        after["running"] = sorted(set(after["running"]) | {identity})
        if identity in _VARIABLES:
            after["variables"][str(_VARIABLES[identity])] = 0
        storage.store(db, character_id, after)
        packets += wire.changes(character_id, before, after, [], [], now_ms)
        return dict(applied=True, packets=packets, definition_id=identity)


def _advance(db, store, character, event_key, increments, fact, *, occurred_at_ms):
    """Complete only an actually accepted current cycle; caller owns facts."""
    guild_id = _member(db, character["id"])
    if guild_id is None:
        return []
    now_ms = _now(db, store)
    packets = synchronize(db, character["id"], now_ms=now_ms)
    rows = db.execute(
        "SELECT * FROM character_guild_daily_quests WHERE character_id=%s "
        "AND completed_at_ms IS NULL FOR UPDATE",
        (character["id"],),
    ).fetchall()
    if type(occurred_at_ms) is not int or occurred_at_ms < 0:
        raise ValueError("Missing authoritative guild quest event time")
    active = [
        row
        for row in rows
        if row["cycle_index"] == cycle(row["definition_id"], now_ms)
        and row["activated_at_ms"] <= occurred_at_ms
    ]
    if not active:
        return packets
    if not storage.record_event(db, character["id"], event_key, fact):
        return packets
    before = storage.load_locked(db, character["id"])
    after = deepcopy(before)
    objectives, completed = [], []
    for row in active:
        identity = row["definition_id"]
        increment = increments.get(identity, 0)
        if type(increment) is not int or increment < 0:
            raise ValueError("Invalid authoritative guild quest increment")
        if not increment:
            continue
        required = 1 if identity == 1391 else 10
        value = min(required, row["progress"] + increment)
        if identity in _VARIABLES:
            after["variables"][str(_VARIABLES[identity])] = value
        done = value >= required
        db.execute(
            "UPDATE character_guild_daily_quests SET progress=%s,completed_at_ms=%s,"
            "earned_guild_id=%s WHERE character_id=%s AND definition_id=%s AND cycle_index=%s",
            (
                value,
                now_ms if done else None,
                guild_id if done else None,
                character["id"],
                identity,
                row["cycle_index"],
            ),
        )
        if not done:
            continue
        after["running"] = [x for x in after["running"] if x != identity]
        after["completed"] = sorted(set(after["completed"]) | {identity})
        after["objectives"] = sorted(set(after["objectives"]) | {_OBJECTIVES[identity]})
        after["completion_dates"][str(identity)] = now_ms
        after["recent"].append(dict(id=identity, date_ms=now_ms))
        objectives.append(_OBJECTIVES[identity])
        completed.append(identity)
        for native in _rules()[str(identity)]["rewards"]:
            reward = dict(native, _guild_id=guild_id, _guild_completion_date_ms=now_ms)
            storage.enqueue_reward(
                db,
                character["id"],
                identity,
                "guild-daily:" + str(row["cycle_index"]),
                str(native["d"]),
                reward,
            )
    after["recent"] = after["recent"][-255:]
    after["tracking"] = [x for x in after["tracking"] if x not in completed]
    storage.store(db, character["id"], after)
    packets += wire.changes(
        character["id"], before, after, objectives, completed, now_ms
    )
    from wakfu_server.achievements.service import drain_rewards

    packets += drain_rewards(db, store, character)
    return packets


def settle_combat(db, store, character, fight, event):
    """Called only with the service's validated winning original-roster event."""
    if not _enabled(db) or _member(db, character["id"]) is None:
        return []
    receipt = db.execute(
        "SELECT payload,created_at FROM character_achievement_events "
        "WHERE character_id=%s AND event_key=%s",
        (character["id"], "fight:" + str(fight.id)),
    ).fetchone()
    if receipt is None or receipt["payload"] != event:
        raise ValueError(
            "Guild combat quest requires the actual achievement settlement receipt"
        )
    actor = fight.actors.get(character["id"])
    if (
        actor is None
        or not actor.controlled
        or actor.owner_id != character["account_id"]
        or actor.team != fight.winner
        or getattr(actor, "pve_withdrawn", False)
    ):
        raise ValueError("Guild quest requires the actual winning human participant")
    from wakfu_server.combat_terminal_metadata import registered_summon_actor_ids
    from wakfu_server.combat_companions import registered_companion_ids

    if character["id"] in registered_summon_actor_ids(fight) | registered_companion_ids(
        fight
    ):
        return []
    defeated = []
    for identity, breed in event["original_monsters"]:
        target = fight.actors.get(identity)
        if (
            target is None
            or target.hp > 0
            or target.controlled
            or target.team == fight.winner
        ):
            raise ValueError("Guild quest requires defeated original monster identity")
        defeated.append((identity, breed, target.effective_level))
    kills = sum(abs(level - actor.effective_level) <= 35 for _, _, level in defeated)
    boss_kill = False
    if event["completed_dungeon_id"] is not None:
        run = db.execute(
            "SELECT r.rooms,e.room_order FROM dungeon_room_encounters e "
            "JOIN dungeon_room_runs r ON r.instance_id=e.instance_id "
            "WHERE e.fight_id=%s AND e.status='victory' AND r.status='completed'",
            (fight.id,),
        ).fetchone()
        if run is not None:
            room = next(
                (room for room in run["rooms"] if room["order"] == run["room_order"]),
                None,
            )
            if room is not None:
                bosses = {
                    row["ref_id"] for row in room["monsters"] if row["role"] == "boss"
                }
                boss_kill = any(
                    breed in bosses and abs(level - actor.effective_level) <= 50
                    for _, breed, level in defeated
                )
    return _advance(
        db,
        store,
        character,
        "guild-daily-combat:" + str(fight.id),
        {1389: kills, 1391: int(boss_kill)},
        dict(
            kind="native_guild_daily_combat",
            fight_id=fight.id,
            original_monsters=[list(row) for row in defeated],
            hero_level=actor.effective_level,
            completed_dungeon_id=event["completed_dungeon_id"],
        ),
        occurred_at_ms=int(receipt["created_at"].timestamp() * 1000),
    )


@lru_cache(maxsize=2048)
def _item_level(reference):
    from wakfu_server import native_catalog
    from wakfu_server.paths import DATA_ROOT

    row = native_catalog.record(
        DATA_ROOT / "item-recycling-metadata.json", "items", reference
    )
    if (
        row is None
        or row.get("reference") != reference
        or type(row.get("item_level")) is not int
    ):
        return None
    return row["item_level"]


def settle_craft(db, store, character, token, *, profession_level):
    """Use only actual completed ordinary item products; no kama craft path."""
    if not _enabled(db) or _member(db, character["id"]) is None:
        return []
    row = db.execute(
        "SELECT * FROM craft_occupations WHERE token=%s AND character_id=%s "
        "AND account_id=%s AND state='completed'",
        (token, character["id"], character["account_id"]),
    ).fetchone()
    if row is None or type(profession_level) is not int or profession_level < 0:
        raise ValueError("Guild quest requires an actual completed item craft")
    products = row["products"]
    count = 0
    for product in products:
        reference, quantity = product["reference"], product["quantity"]
        if type(reference) is not int or type(quantity) is not int or quantity <= 0:
            raise ValueError("Invalid durable crafted product")
        level = _item_level(reference)
        if level is not None and abs(level - profession_level) <= 35:
            count += quantity
    return _advance(
        db,
        store,
        character,
        "guild-daily-craft:" + str(token),
        {1390: count},
        dict(
            kind="native_guild_daily_craft",
            token=str(token),
            recipe_id=row["recipe_id"],
            profession_id=row["profession_id"],
            profession_level=profession_level,
            products=products,
        ),
        occurred_at_ms=int(row["finished_at"].timestamp() * 1000),
    )


def activation_dates(db, character_id):
    """Restore only actual accepted current-cycle native activation clocks."""
    if not _enabled(db):
        return {}
    now_ms = _now(db)
    rows = db.execute(
        "SELECT DISTINCT ON(definition_id) definition_id,cycle_index,activated_at_ms "
        "FROM character_guild_daily_quests WHERE character_id=%s "
        "ORDER BY definition_id,cycle_index DESC",
        (character_id,),
    ).fetchall()
    return {
        row["definition_id"]: row["activated_at_ms"]
        for row in rows
        if row["cycle_index"] == cycle(row["definition_id"], now_ms)
    }


def trackable(db, character_id, identity):
    if (
        identity not in _OBJECTIVES
        or not _enabled(db)
        or _member(db, character_id) is None
    ):
        return False
    now_ms = _now(db)
    return (
        db.execute(
            "SELECT 1 FROM character_guild_daily_quests WHERE character_id=%s "
            "AND definition_id=%s AND cycle_index=%s AND completed_at_ms IS NULL",
            (character_id, identity, cycle(identity, now_ms)),
        ).fetchone()
        is not None
    )
