"""Durable limited mission selection, frozen once per account and period."""

from wakfu_server.character_levels import MAX_CHARACTER_LEVEL
import hashlib
from datetime import datetime, timezone
from .schedules import period_key, DEFAULT_TIMEZONE

DEFAULT_COUNTS = {"daily": 2, "weekly": 6, "mission": 2}


def managed(definition):
    return definition["kind"] not in {
        "achievement",
        "onboarding",
        "pvp",
        "almanax",
    } and definition["schedule"]["type"] in {"once", "daily", "weekly"}


def group_key(definition):
    recurrence = definition["schedule"]["type"]
    return recurrence if recurrence in {"daily", "weekly"} else "mission"


def ensure_for_character(
    db, account_id, character_id, level, at=None, *, wait_for_lock=True
):
    if type(wait_for_lock) is not bool:
        raise ValueError("Invalid assignment lock policy")
    at = at or datetime.now(timezone.utc)
    if not db.execute(
        "SELECT 1 FROM sessions WHERE account_id=%s AND character_id=%s AND expires_at>CURRENT_TIMESTAMP",
        (account_id, character_id),
    ).fetchone():
        return 0
    lock_key = "objective-assignments:" + str(account_id)
    if wait_for_lock:
        db.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", (lock_key,))
    elif not db.execute(
        "SELECT pg_try_advisory_xact_lock(hashtextextended(%s,0)) AS locked",
        (lock_key,),
    ).fetchone()["locked"]:
        # A scheduler batch already holds other account locks. Never wait on a
        # foreground transaction that may need one of them; retry next pass.
        return 0
    row = db.execute(
        "SELECT value FROM settings WHERE name='objectives_assignment_counts'"
    ).fetchone()
    counts = dict(DEFAULT_COUNTS)
    if row:
        counts.update(
            {
                k: v
                for k, v in row["value"].items()
                if k in counts and type(v) is int and 0 <= v <= 20
            }
        )
    completed = {
        r["definition_key"]
        for r in db.execute(
            "SELECT definition_key FROM objectives_account_progress WHERE account_id=%s AND completed_at IS NOT NULL",
            (account_id,),
        ).fetchall()
    }
    candidates = db.execute(
        "SELECT key,definition FROM objectives_definitions WHERE (definition->>'enabled')::boolean AND definition->>'kind' NOT IN ('achievement','onboarding','pvp','almanax') AND definition->'schedule'->>'type' IN ('once','daily','weekly') ORDER BY key"
    ).fetchall()
    created = 0
    for group, count in counts.items():
        schedule = {
            "type": group if group != "mission" else "once",
            "timezone": DEFAULT_TIMEZONE,
        }
        period = period_key(schedule, at)
        db.execute(
            "INSERT INTO objectives_assignment_periods(account_id,group_key,period_key,character_id,level) VALUES(%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
            (account_id, group, period, character_id, level),
        )
        receipt = db.execute(
            "SELECT level FROM objectives_assignment_periods WHERE account_id=%s AND group_key=%s AND period_key=%s",
            (account_id, group, period),
        ).fetchone()
        # Increasing a quota appends eligible objectives to the same frozen
        # period. Existing assignments and progress never get replaced.
        selection_level = receipt["level"] if group != "mission" else level
        assigned = {
            r["definition_key"]
            for r in db.execute(
                "SELECT definition_key FROM objectives_assignments WHERE account_id=%s AND group_key=%s AND period_key=%s",
                (account_id, group, period),
            ).fetchall()
        }
        remaining = (
            count - len(assigned - completed)
            if group == "mission"
            else count - len(assigned)
        )
        if remaining <= 0:
            continue
        eligible = []
        for row in candidates:
            rule = row["definition"]
            band = rule.get(
                "level_range", {"minimum": 1, "maximum": MAX_CHARACTER_LEVEL}
            )
            if (
                not managed(rule)
                or group_key(rule) != group
                or not band["minimum"] <= selection_level <= band["maximum"]
            ):
                continue
            if row["key"] in assigned or (
                group == "mission" and row["key"] in completed
            ):
                continue
            if not set(rule.get("prerequisite_keys", ())) <= completed:
                continue
            eligible.append(row["key"])
        eligible.sort(
            key=lambda key: hashlib.sha256(
                f"{account_id}:{group}:{period}:{key}".encode()
            ).digest()
        )
        for key in eligible[: max(0, remaining)]:
            db.execute(
                "INSERT INTO objectives_assignments(account_id,group_key,period_key,definition_key) VALUES(%s,%s,%s,%s)",
                (account_id, group, period, key),
            )
            created += 1
    return created


def ensure_online(db, limit=100):
    if type(limit) is not int or not 1 <= limit <= 1000:
        raise ValueError("Invalid assignment batch size")
    cursor = db.execute(
        "SELECT s.account_id,s.character_id,c.level FROM sessions s JOIN characters c ON c.id=s.character_id AND c.account_id=s.account_id WHERE s.expires_at>CURRENT_TIMESTAMP AND c.deleted_at IS NULL ORDER BY s.account_id"
    )
    created = 0
    while True:
        rows = cursor.fetchmany(limit)
        if not rows:
            return created
        created += sum(
            ensure_for_character(
                db, r["account_id"], r["character_id"], r["level"], wait_for_lock=False
            )
            for r in rows
        )


def is_assigned(db, account_id, definition_key, period):
    return (
        db.execute(
            "SELECT 1 FROM objectives_assignments WHERE account_id=%s AND definition_key=%s AND period_key=%s",
            (account_id, definition_key, period),
        ).fetchone()
        is not None
    )


def assigned_level(db, account_id, definition_key, period):
    row = db.execute(
        "SELECT p.level FROM objectives_assignments a JOIN objectives_assignment_periods p USING(account_id,group_key,period_key) WHERE a.account_id=%s AND a.definition_key=%s AND a.period_key=%s",
        (account_id, definition_key, period),
    ).fetchone()
    return row["level"] if row else None


def visible_keys(db, account_id, at=None):
    at = at or datetime.now(timezone.utc)
    today = period_key({"type": "daily", "timezone": DEFAULT_TIMEZONE}, at)
    week = period_key({"type": "weekly", "timezone": DEFAULT_TIMEZONE}, at)
    return {
        r["definition_key"]
        for r in db.execute(
            "SELECT definition_key FROM objectives_assignments WHERE account_id=%s AND ((group_key='daily' AND period_key=%s) OR (group_key='weekly' AND period_key=%s) OR group_key='mission')",
            (account_id, today, week),
        ).fetchall()
    }


def visible(db, account_id, definition, at=None):
    return not managed(definition) or definition["key"] in visible_keys(
        db, account_id, at
    )
