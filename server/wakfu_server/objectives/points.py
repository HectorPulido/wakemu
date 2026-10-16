"""Append-only, exactly-once account points from completed game objectives."""
from datetime import datetime, timezone, date, timedelta
from .rankings import week_key

DEFAULT_WEIGHTS = {
    "daily": 20,
    "weekly": 100,
    "public_hunt": 100,
    "hourly_pvp_participation": 10,
    "hourly_pvp_win": 50,
    "achievement": 10,
    "onboarding": 10,
    "mission": 20,
    "almanax": 20,
}


def weights(db):
    row = db.execute(
        "SELECT value FROM settings WHERE name='objectives_points_weights'"
    ).fetchone()
    result = dict(DEFAULT_WEIGHTS)
    if row:
        result.update(
            {
                k: v
                for k, v in row["value"].items()
                if k in result and type(v) is int and 0 <= v <= 1000000
            }
        )
    return result


def category(definition):
    if definition["kind"] in {"achievement", "onboarding", "almanax"}:
        return definition["kind"]
    schedule = definition["schedule"]["type"]
    return schedule if schedule in {"daily", "weekly"} else "mission"


def definition_points(db, definition):
    return weights(db)[category(definition)]


def award_points(
    db,
    account_id,
    source_key,
    points,
    *,
    character_id=None,
    level=None,
    occurred_at=None,
    category="mission",
    title=None
):
    if (
        type(points) is not int
        or not 0 <= points <= 1000000
        or not isinstance(source_key, str)
        or not 1 <= len(source_key) <= 512
    ):
        raise ValueError("Invalid objective points receipt")
    at = occurred_at or datetime.now(timezone.utc)
    actor = db.execute(
        "SELECT id,level FROM characters WHERE account_id=%s AND id=%s AND deleted_at IS NULL",
        (account_id, character_id),
    ).fetchone()
    if actor is None:
        raise ValueError("Points beneficiary must belong to the account")
    original_week = week_key(at)
    week = original_week
    db.execute(
        "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
        ("objective-points:" + week,),
    )
    if db.execute(
        "SELECT 1 FROM objectives_weekly_finalizations WHERE week_key=%s AND bracket='all'",
        (week,),
    ).fetchone():
        week = week_key()
        while True:
            db.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                ("objective-points:" + week,),
            )
            if not db.execute(
                "SELECT 1 FROM objectives_weekly_finalizations WHERE week_key=%s AND bracket='all'",
                (week,),
            ).fetchone():
                break
            week = (date.fromisoformat(week) + timedelta(days=7)).isoformat()
    row = db.execute(
        "INSERT INTO objectives_points(account_id,source_key,points,category,character_id,level,week_key,original_week_key,late_credit,occurred_at) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(account_id,source_key) DO NOTHING RETURNING id",
        (
            account_id,
            source_key,
            points,
            category,
            actor["id"],
            level or actor["level"],
            week,
            original_week,
            week != original_week,
            at,
        ),
    ).fetchone()
    if row:
        from .notices import enqueue, CATEGORY_TITLES

        enqueue(
            db,
            account_id,
            source_key,
            title or CATEGORY_TITLES.get(category, "Mission"),
            points,
            at=at,
        )
        for char in db.execute(
            "SELECT id FROM characters WHERE account_id=%s AND deleted_at IS NULL",
            (account_id,),
        ).fetchall():
            db.execute(
                "SELECT pg_notify('wakemu_objectives_updates',%s)", (str(char["id"]),)
            )
    return row is not None


def award_configured(
    db,
    account_id,
    source_key,
    category,
    *,
    character_id=None,
    level=None,
    occurred_at=None,
    title=None
):
    return award_points(
        db,
        account_id,
        source_key,
        weights(db)[category],
        character_id=character_id,
        level=level,
        occurred_at=occurred_at,
        category=category,
        title=title,
    )


def award_completion(db, event, definition, period):
    return award_configured(
        db,
        event["account_id"],
        "objective:" + definition["key"] + ":" + period,
        category(definition),
        character_id=event["character_id"],
        level=event["character_level"],
        occurred_at=event["occurred_at"],
        title=definition["title"],
    )


def list_rankings(db, week=None, bracket=None, limit=100):
    from datetime import date

    week = week or week_key()
    if (
        date.fromisoformat(week).weekday() != 0
        or type(limit) is not int
        or not 1 <= limit <= 1000
    ):
        raise ValueError("Invalid ranking request")
    if bracket not in (None, "all"):
        return []
    return db.execute(
        "WITH totals AS (SELECT account_id,sum(points)::bigint AS points,max(occurred_at) AS completed_at FROM objectives_points WHERE week_key=%s GROUP BY account_id), ranked AS (SELECT *,row_number() OVER(ORDER BY points DESC,completed_at,account_id) AS rank FROM totals) SELECT ranked.*,'all'::text AS bracket,latest.character_id,latest.level FROM ranked JOIN LATERAL (SELECT c.id AS character_id,c.level FROM characters c WHERE c.account_id=ranked.account_id AND c.deleted_at IS NULL ORDER BY (c.id=(SELECT p.character_id FROM objectives_points p WHERE p.account_id=ranked.account_id AND p.week_key=%s ORDER BY p.occurred_at DESC,p.id DESC LIMIT 1)) DESC,c.id LIMIT 1) latest ON true ORDER BY rank LIMIT %s",
        (week, week, limit),
    ).fetchall()
