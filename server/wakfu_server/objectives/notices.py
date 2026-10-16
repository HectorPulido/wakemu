"""Durable account completion feedback; World alone sends native chat packets."""
import re
from datetime import datetime, timezone

CATEGORY_TITLES = {
    "daily": "Daily challenge",
    "weekly": "Weekly challenge",
    "public_hunt": "World hunt",
    "hourly_pvp_participation": "Hourly PvP participation",
    "hourly_pvp_win": "Hourly PvP victory",
    "achievement": "Achievement",
    "onboarding": "First steps",
    "mission": "Mission",
    "almanax": "Almanax",
}


def available(db):
    """Allow service binaries to start safely before the additive migration."""
    return (
        db.execute(
            "SELECT to_regclass('objectives_completion_notices') AS relation"
        ).fetchone()["relation"]
        is not None
    )


def enqueue(db, account_id, source_key, title, points, *, at=None):
    """Reserve one future notice in the same transaction as its completion."""
    if type(account_id) is not int or account_id <= 0:
        raise ValueError("Invalid completion notice account")
    if type(source_key) is not str or not 1 <= len(source_key) <= 512:
        raise ValueError("Invalid completion notice source")
    if type(title) is not str or not title.strip():
        raise ValueError("Invalid completion notice title")
    if type(points) is not int or not 0 <= points <= 1000000:
        raise ValueError("Invalid completion notice points")
    title = re.sub(r"[\x00-\x1f\x7f-\x9f]+", " ", title).strip()[:256]
    if not title:
        raise ValueError("Invalid completion notice title")
    at = at or datetime.now(timezone.utc)
    if at.tzinfo is None:
        raise ValueError("Completion notice timestamp requires timezone")
    if not available(db):
        return False
    row = db.execute(
        "INSERT INTO objectives_completion_notices(account_id,source_key,title,points,occurred_at) "
        "VALUES(%s,%s,%s,%s,%s) ON CONFLICT(account_id,source_key) DO NOTHING RETURNING id",
        (account_id, source_key, title, points, at),
    ).fetchone()
    return row is not None


def message(row):
    return f"Objective completed: {row['title']} (+{row['points']} points)."


def deliver(db, account_id, generation, character_id, send_notice, *, limit=20):
    """Send pending feedback through the current session's owning dispatcher.

    The caller owns the transaction. A failed socket send leaves the row pending;
    ordinary polling, event replays and character switches cannot resend receipts.
    """
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("Invalid completion notice batch size")
    if not available(db):
        return 0
    owner = db.execute(
        "SELECT s.character_id FROM sessions s JOIN characters c ON c.id=s.character_id "
        "WHERE s.account_id=%s AND s.generation=%s AND s.character_id=%s "
        "AND s.expires_at>CURRENT_TIMESTAMP AND c.account_id=s.account_id AND c.deleted_at IS NULL "
        "FOR UPDATE OF s",
        (account_id, generation, character_id),
    ).fetchone()
    if owner is None:
        return 0
    rows = db.execute(
        "SELECT id,title,points FROM objectives_completion_notices WHERE account_id=%s "
        "AND delivered_at IS NULL ORDER BY id LIMIT %s FOR UPDATE SKIP LOCKED",
        (account_id, limit),
    ).fetchall()
    for row in rows:
        send_notice(message(row))
        db.execute(
            "UPDATE objectives_completion_notices SET delivered_at=CURRENT_TIMESTAMP,delivered_character_id=%s WHERE id=%s",
            (character_id, row["id"]),
        )
    return len(rows)
