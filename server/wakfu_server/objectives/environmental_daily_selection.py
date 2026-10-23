"""Persisted Wakemu daily hunt rotation, independent of NPC acceptance routing.

The original server seed is unrecovered. One UTC-day/category choice uses the
sorted qualified immutable pool; level checks never reroll that global choice.
"""
from . import environmental_presence as presence
from .environmental_runtime import integer
from .environmental_service import _lock_owner

DAY_MS = 86400000
POLICY = "wakemu.daily-hunter-utc-sorted-rotation-v1"


def _live(character):
    map_id = integer(character.get("map_id"), "map", minimum=1)
    instance_id = integer(character.get("instance_id", 0), "instance")
    occupied = presence.capture(map_id, instance_id)
    if occupied is None:
        return None
    identity = occupied[0].live_identity(character_id=character["id"])
    if identity is None:
        return None
    generation, actual = identity
    if any(
        actual.get(key, 0) != character.get(key, 0)
        for key in ("id", "account_id", "map_id", "instance_id")
    ):
        return None
    return occupied, generation, map_id, instance_id


def _current(live, character):
    occupied, generation, map_id, instance_id = live
    if not presence.current(occupied, map_id, instance_id):
        return False
    identity = occupied[0].live_identity(character_id=character["id"])
    return (
        identity is not None
        and identity[0] == generation
        and all(
            identity[1].get(key, 0) == character.get(key, 0)
            for key in ("id", "account_id", "map_id", "instance_id")
        )
    )


def select_for_character(db, store, character, *, now_ms=None):
    """Select only today's offers for an owned selected, actually present player.

    The caller owns the transaction. Vacant/stale presence returns before SQL.
    No journal acceptance, packet, reward or historical selection is created.
    """
    live = _live(character)
    if live is None:
        return ()
    current_ms = integer(int(store.now().timestamp() * 1000), "clock")
    now_ms = current_ms if now_ms is None else integer(now_ms, "clock")
    if now_ms // DAY_MS != current_ms // DAY_MS:
        raise ValueError("Daily hunter selection cannot backfill another UTC day")
    _lock_owner(store, db, character["account_id"], live[1], character["id"])
    actual = store.character(character["account_id"], character["id"], db)
    if not _current(live, character) or any(
        actual.get(key, 0) != character.get(key, 0) for key in ("map_id", "instance_id")
    ):
        return ()
    active = db.execute(
        "SELECT a.pool_version,p.interpretation_policy FROM recurring_hunter_daily_active a "
        "JOIN recurring_hunter_daily_pools p USING(pool_version) WHERE a.singleton AND a.enabled AND p.sealed"
    ).fetchone()
    if active is None:
        return ()
    if active["interpretation_policy"] != POLICY:
        raise ValueError("Unsupported daily hunter selector policy")
    day = now_ms // DAY_MS
    categories = db.execute(
        "SELECT category_id FROM recurring_hunter_daily_members WHERE pool_version=%s "
        "UNION SELECT category_id FROM recurring_hunter_daily_choices WHERE utc_day=%s ORDER BY category_id",
        (active["pool_version"], day),
    ).fetchall()
    result = []
    for category in categories:
        category_id = category["category_id"]
        db.execute("SELECT pg_advisory_xact_lock(%s,%s)", (294, category_id))
        if not _current(live, character):
            raise ValueError("Daily hunter owner presence changed during selection")
        choice = chosen_for_receipt(db, category_id=category_id, occurred_at_ms=now_ms)
        if choice is None:
            members = db.execute(
                "SELECT definition_id,version FROM recurring_hunter_daily_members "
                "WHERE pool_version=%s AND category_id=%s ORDER BY definition_id,version",
                (active["pool_version"], category_id),
            ).fetchall()
            if not members:
                continue
            selected = members[day % len(members)]
            choice = db.execute(
                "INSERT INTO recurring_hunter_daily_choices "
                "(category_id,utc_day,pool_version,definition_id,version,selected_at_ms) "
                "VALUES(%s,%s,%s,%s,%s,%s) RETURNING *",
                (
                    category_id,
                    day,
                    active["pool_version"],
                    selected["definition_id"],
                    selected["version"],
                    now_ms,
                ),
            ).fetchone()
        contract = db.execute(
            "SELECT minimum_level FROM recurring_hunter_contracts "
            "WHERE definition_id=%s AND version=%s",
            (choice["definition_id"], choice["version"]),
        ).fetchone()
        result.append(
            dict(choice, eligible=actual["level"] >= contract["minimum_level"])
        )
    if not _current(live, character):
        raise ValueError("Daily hunter owner presence changed before completion")
    return tuple(result)


def chosen_for_receipt(
    db, *, category_id, occurred_at_ms, definition_id=None, version=None
):
    """Read an existing pinned choice; never create or backfill a receipt's day.

    This is source selection proof only. The acceptance backend must separately
    authenticate the receipt's owner, producer, timestamp and contract minimum.
    """
    category_id = integer(category_id, "category", minimum=1)
    day = integer(occurred_at_ms, "receipt clock") // DAY_MS
    row = db.execute(
        "SELECT * FROM recurring_hunter_daily_choices WHERE category_id=%s AND utc_day=%s",
        (category_id, day),
    ).fetchone()
    if (
        row is None
        or (definition_id is not None and row["definition_id"] != definition_id)
        or (version is not None and row["version"] != version)
    ):
        return None
    return row
