"""Authoritative account achievement observations from persisted native progress."""
import hashlib
from .catalog import canonical

CHARACTER_EVENT = "account_character_level_progressed"
PROFESSION_EVENT = "account_profession_level_progressed"
ABSOLUTE_EVENTS = frozenset({CHARACTER_EVENT, PROFESSION_EVENT})


def definitions():
    rows = []
    for threshold in (50, 100, 150, 200, 245):
        rows.append(
            _definition(
                f"characters.level.{threshold}",
                f"Reach character level {threshold}",
                f"Reach level {threshold} with any undeleted character on your account."
                + (
                    " This milestone becomes attainable when the server supports level 245; the current cap is 200."
                    if threshold == 245
                    else ""
                ),
                CHARACTER_EVENT,
                threshold,
                1,
            )
        )
    for count in (2, 3):
        rows.append(
            _definition(
                f"characters.level.200.count.{count}",
                f"{count} characters at level 200",
                f"Have {count} distinct undeleted characters at level 200 or higher on your account.",
                CHARACTER_EVENT,
                200,
                count,
            )
        )
    for count in (1, 2, 3):
        rows.append(
            _definition(
                f"professions.level.100.count.{count}",
                f"{count} profession{'s' if count != 1 else ''} at level 100",
                f"Reach level 100 in {count} distinct account profession{'s' if count != 1 else ''}. The same profession is counted once across heroes.",
                PROFESSION_EVENT,
                100,
                count,
            )
        )
    return rows


def _definition(suffix, title, description, event, threshold, target):
    return dict(
        key="progression-v1." + suffix,
        title=title,
        description=description,
        kind="achievement",
        scope="account",
        enabled=True,
        objectives=[
            dict(
                key="count",
                event=event,
                filters={"minimum_level": threshold},
                target=target,
            )
        ],
        schedule={"type": "once", "timezone": "America/Bogota"},
        prerequisite_keys=[],
        rewards=[{"kind": "scaled", "policy_key": "content-v1.exploration"}],
    )


def native_count(db, account_id, kind, threshold):
    if kind == CHARACTER_EVENT:
        return db.execute(
            "SELECT count(*) AS count FROM characters WHERE account_id=%s "
            "AND deleted_at IS NULL AND level>=%s",
            (account_id, threshold),
        ).fetchone()["count"]
    if kind == PROFESSION_EVENT:
        from wakfu_server.profession_wire import level

        return sum(
            level(row["xp"]) >= threshold
            for row in db.execute(
                "SELECT xp FROM account_professions WHERE account_id=%s", (account_id,)
            ).fetchall()
        )
    raise ValueError("Unsupported account progression fact")


def validate_fact(db, account_id, payload):
    """Ingress cannot invent an aggregate; capture its persisted value now."""
    if (
        set(payload) != {"kind", "minimum_level", "count"}
        or payload["kind"] not in ABSOLUTE_EVENTS
        or type(payload["minimum_level"]) is not int
        or not 1 <= payload["minimum_level"] <= 1000
        or type(payload["count"]) is not int
        or not 0 <= payload["count"] <= 2**31 - 1
    ):
        raise ValueError("Invalid account progression fact")
    if payload["count"] != native_count(
        db, account_id, payload["kind"], payload["minimum_level"]
    ):
        raise ValueError(
            "Account progression fact differs from persisted native progress"
        )


def observe(store, account_id, generation, character_id):
    """A bounded World poll includes historical eligible progress after login."""
    from . import repository

    with store.connection() as db:
        owner = db.execute(
            "SELECT c.level FROM sessions s JOIN characters c ON c.id=s.character_id "
            "WHERE s.account_id=%s AND s.generation=%s AND s.character_id=%s "
            "AND s.expires_at>CURRENT_TIMESTAMP AND c.account_id=s.account_id AND c.deleted_at IS NULL "
            "FOR UPDATE OF s",
            (account_id, generation, character_id),
        ).fetchone()
        if owner is None:
            return 0
        candidates = db.execute(
            "SELECT d.key,d.revision,o->>'event' AS event,o->'filters'->>'minimum_level' AS threshold "
            "FROM objectives_definitions d CROSS JOIN LATERAL jsonb_array_elements(d.definition->'objectives') o "
            "WHERE (d.definition->>'enabled')::boolean AND o->>'event'=ANY(%s::text[]) ORDER BY d.key",
            (list(ABSOLUTE_EVENTS),),
        ).fetchall()
        groups = {}
        for row in candidates:
            threshold = int(row["threshold"])
            groups.setdefault((row["event"], threshold), []).append(
                [row["key"], row["revision"]]
            )
        published = 0
        for (kind, threshold), versions in sorted(groups.items()):
            count = native_count(db, account_id, kind, threshold)
            if not count:
                continue
            digest = hashlib.sha256(canonical(versions).encode()).hexdigest()[:20]
            identity = f"account-progress:{kind}:{threshold}:{count}:{digest}"
            # Account-level source identity avoids a new event for every hero or poll.
            if db.execute(
                "SELECT 1 FROM objectives_account_sources WHERE account_id=%s AND source_key=%s",
                (account_id, kind + ":" + identity),
            ).fetchone():
                continue
            if db.execute(
                "SELECT 1 FROM objectives_events WHERE account_id=%s AND event_key=%s",
                (account_id, identity),
            ).fetchone():
                continue
            result = repository.enqueue(
                db,
                account_id,
                character_id,
                identity,
                {"kind": kind, "minimum_level": threshold, "count": count},
            )
            published += not result["replayed"]
        return published
