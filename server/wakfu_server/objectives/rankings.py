"""Trusted weekly challenge scores and once-only winner entitlements."""
from datetime import datetime, timezone, timedelta, date
from psycopg.types.json import Jsonb
from .catalog import integer
from .schedules import DEFAULT_TIMEZONE
from zoneinfo import ZoneInfo


def week_key(at=None):
    current = (
        (at or datetime.now(timezone.utc)).astimezone(ZoneInfo(DEFAULT_TIMEZONE)).date()
    )
    return (current - timedelta(days=current.weekday())).isoformat()


def record_attempt(db, event):
    payload = event["payload"]
    if (
        payload["kind"] != "challenge_completed"
        or not payload.get("won")
        or payload.get("ranked") is False
    ):
        return False
    attempt = db.execute(
        "SELECT r.*,f.status AS fight_status FROM objectives_challenge_runs r JOIN combat_fights f ON f.id=r.fight_id WHERE r.attempt_id=%s",
        (payload["attempt_id"],),
    ).fetchone()
    if (
        attempt is None
        or attempt["status"] != "won"
        or attempt["fight_status"] != "finished"
        or attempt["winner_team"] != 0
        or attempt["test_mode"]
    ):
        raise ValueError("Challenge attempt lacks authoritative normal victory receipt")
    if (
        attempt["owner_account_id"] != event["account_id"]
        or attempt["character_id"] != event["character_id"]
    ):
        raise ValueError("Challenge attempt owner mismatch")
    for field in ("profile_key", "week_key", "bracket", "level", "turns"):
        if (
            type(payload.get(field)) is not type(attempt[field])
            or payload[field] != attempt[field]
        ):
            raise ValueError("Challenge score conflicts with durable attempt receipt")
    integer(attempt["turns"], 2**31 - 1)
    if attempt["week_key"] != week_key(event["occurred_at"]):
        raise ValueError("Challenge attempt belongs to a different week")
    if db.execute(
        "SELECT 1 FROM objectives_weekly_finalizations WHERE week_key=%s AND bracket=%s",
        (attempt["week_key"], attempt["bracket"]),
    ).fetchone():
        raise ValueError("Challenge week is already finalized")
    if not db.execute(
        "INSERT INTO objectives_ranked_attempts(attempt_id,event_id) VALUES(%s,%s) ON CONFLICT DO NOTHING RETURNING attempt_id",
        (attempt["attempt_id"], event["id"]),
    ).fetchone():
        return False
    points = max(1, 10000 // attempt["turns"])
    db.execute(
        "INSERT INTO objectives_weekly_scores(week_key,profile_key,bracket,account_id,character_id,attempt_id,points,turns,level,completed_at) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
        "ON CONFLICT(week_key,profile_key,bracket,account_id) DO UPDATE SET character_id=EXCLUDED.character_id,attempt_id=EXCLUDED.attempt_id,points=EXCLUDED.points,turns=EXCLUDED.turns,level=EXCLUDED.level,completed_at=EXCLUDED.completed_at "
        "WHERE (EXCLUDED.points,-EXCLUDED.turns)<>(objectives_weekly_scores.points,-objectives_weekly_scores.turns) AND EXCLUDED.points>objectives_weekly_scores.points "
        "OR (EXCLUDED.points=objectives_weekly_scores.points AND (EXCLUDED.turns,EXCLUDED.completed_at,EXCLUDED.attempt_id)<(objectives_weekly_scores.turns,objectives_weekly_scores.completed_at,objectives_weekly_scores.attempt_id))",
        (
            attempt["week_key"],
            attempt["profile_key"],
            attempt["bracket"],
            event["account_id"],
            event["character_id"],
            attempt["attempt_id"],
            points,
            attempt["turns"],
            attempt["level"],
            attempt["settled_at"],
        ),
    )
    return True


def list_rankings(db, week=None, bracket=None, limit=100):
    from .points import list_rankings as account_rankings

    return account_rankings(db, week, bracket, limit)


def finalize_weeks(db, now=None):
    """Snapshot top three account point totals through the ordinary World outbox."""
    from .repository import reserve_rewards

    current_week = week_key(now)
    groups = db.execute(
        "SELECT DISTINCT s.week_key,'all'::text AS bracket FROM objectives_points s WHERE s.week_key<%s "
        "AND NOT EXISTS(SELECT 1 FROM objectives_weekly_finalizations f WHERE f.week_key=s.week_key AND f.bracket='all') "
        "AND NOT EXISTS(SELECT 1 FROM objectives_events e WHERE e.processed_at IS NULL AND e.attempts<5 "
        "AND e.occurred_at < ((s.week_key::date+7)::timestamp AT TIME ZONE 'America/Bogota')) "
        "ORDER BY s.week_key LIMIT 20",
        (current_week,),
    ).fetchall()
    if not groups:
        return 0
    policy = db.execute(
        "SELECT key,policy,revision FROM objectives_reward_policies WHERE key='weekly-ranking-v1'"
    ).fetchone()
    if policy is None:
        raise ValueError("Weekly ranking reward policy is unavailable")
    definition = {
        "key": "weekly-ranking-awards",
        "title": "Weekly adventure ranking",
        "description": "Weekly ranking winner rewards.",
        "kind": "recurring",
        "enabled": False,
        "scope": "account",
        "objectives": [
            {
                "key": "rank",
                "event": "weekly_ranking_finalized",
                "filters": {},
                "target": 1,
            }
        ],
        "schedule": {"type": "weekly", "timezone": DEFAULT_TIMEZONE},
        "rewards": [{"kind": "scaled", "policy_key": "weekly-ranking-v1"}],
        "prerequisite_keys": [],
    }
    db.execute(
        "INSERT INTO objectives_definitions(key,definition,revision) VALUES(%s,%s,1) ON CONFLICT DO NOTHING",
        (definition["key"], Jsonb(definition)),
    )
    revision = db.execute(
        "SELECT revision FROM objectives_definitions WHERE key=%s", (definition["key"],)
    ).fetchone()["revision"]
    completed = 0
    for group in groups:
        db.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
            ("objective-points:" + group["week_key"],),
        )
        if db.execute(
            "SELECT 1 FROM objectives_weekly_finalizations WHERE week_key=%s AND bracket='all'",
            (group["week_key"],),
        ).fetchone():
            continue
        winners = list_rankings(db, group["week_key"], group["bracket"], 3)
        period = group["week_key"] + ":" + group["bracket"]
        for winner in winners:
            account_receipt = db.execute(
                "INSERT INTO objectives_account_progress(account_id,definition_key,period_key,definition_revision,counters,completed_at,reward_character_id) "
                "VALUES(%s,%s,%s,%s,%s,CURRENT_TIMESTAMP,%s) ON CONFLICT DO NOTHING RETURNING account_id",
                (
                    winner["account_id"],
                    definition["key"],
                    period,
                    revision,
                    Jsonb({"rank": 1}),
                    winner["character_id"],
                ),
            ).fetchone()
            if account_receipt is None:
                continue
            db.execute(
                "INSERT INTO objectives_progress(character_id,definition_key,period_key,definition_revision,counters,completed_at) VALUES(%s,%s,%s,%s,%s,CURRENT_TIMESTAMP) ON CONFLICT DO NOTHING",
                (
                    winner["character_id"],
                    definition["key"],
                    period,
                    revision,
                    Jsonb({"rank": 1}),
                ),
            )
            reserve_rewards(
                db,
                winner["character_id"],
                definition,
                period,
                level=winner["level"],
                policies={policy["key"]: policy},
            )
            for character in db.execute(
                "SELECT id FROM characters WHERE account_id=%s AND deleted_at IS NULL",
                (winner["account_id"],),
            ).fetchall():
                db.execute(
                    "SELECT pg_notify('wakemu_objectives_updates',%s)",
                    (str(character["id"]),),
                )
        snapshot = {
            "winners": [
                {
                    k: (v.isoformat() if isinstance(v, datetime) else v)
                    for k, v in winner.items()
                }
                for winner in winners
            ],
            "policy_key": policy["key"],
            "policy_revision": policy["revision"],
        }
        db.execute(
            "INSERT INTO objectives_weekly_finalizations(week_key,bracket,status,snapshot) VALUES(%s,%s,'awarded',%s)",
            (group["week_key"], group["bracket"], Jsonb(snapshot)),
        )
        completed += 1
    return completed
