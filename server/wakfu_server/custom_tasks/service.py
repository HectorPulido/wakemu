"""Owned, transaction-scoped custom task counters and earned entitlements.

No client packet may call settle directly. The gameplay adapter must prove the
original dead actor roster or successful committed seed placement and authorize
the character/session. This module only fences durable character ownership.
It acquires no account lock: callers already holding character locks (planting)
must never invert account-before-character lock order. Caller owns commit and
must publish returned completions only after commit. No rewards are delivered
here; outbox rows are earned entitlements for a separately qualified grant path.
"""
from psycopg.pq import TransactionStatus
from psycopg.types.json import Jsonb
from . import catalog, engine


def _owner(db, account_id, character_id, lock):
    if db.info.transaction_status != TransactionStatus.INTRANS:
        raise ValueError("Custom tasks require an active transaction")
    for value in (account_id, character_id):
        if type(value) is not int or not 0 < value < 2**63:
            raise ValueError("Invalid custom task owner")
    suffix = " FOR UPDATE" if lock else ""
    row = db.execute(
        "SELECT id FROM characters WHERE id=%s AND account_id=%s AND deleted_at IS NULL"
        + suffix,
        (character_id, account_id),
    ).fetchone()
    if row is None:
        raise ValueError("Custom task character is not owned by account")


def _definitions(db, definitions):
    return catalog.validate(definitions, db=db)


def settle(db, account_id, character_id, event_key, event, definitions=None):
    """Reserve one authoritative fact set and advance enabled tasks atomically.

    Disabled tasks never count events retroactively. Same-key semantic edits
    reject once a progress row exists; use a new task key for a new objective.
    Exact event replays are no-ops, conflicting facts reject even if all tasks
    are disabled. Completion and reward reservation occur only once per key.
    """
    from . import external

    if external.enabled():
        payload, _ = engine.event_signature(event)
        if event_key != engine.canonical_event_key(payload):
            raise ValueError(
                "Custom task event key does not match canonical source identity"
            )
        return external.enqueue_fact(db, account_id, character_id, event_key, payload)
    rules = _definitions(db, definitions)
    catalog.text(event_key, 256)
    payload, signature = engine.event_signature(event)
    if event_key != engine.canonical_event_key(payload):
        raise ValueError(
            "Custom task event key does not match canonical source identity"
        )
    _owner(db, account_id, character_id, True)
    rows = db.execute(
        "SELECT * FROM character_custom_task_progress WHERE character_id=%s",
        (character_id,),
    ).fetchall()
    prior = {row["task_key"]: row for row in rows}
    # Validate immutable task semantics before reserving any new event.
    for key, row in prior.items():
        if key in rules and row["definition_signature"] != catalog.signature(
            rules[key]
        ):
            raise ValueError(
                "Custom task key reused with different objective or rewards"
            )
    inserted = db.execute(
        "INSERT INTO character_custom_task_events(character_id,event_key,signature,payload) "
        "VALUES (%s,%s,%s,%s) ON CONFLICT DO NOTHING RETURNING event_key",
        (character_id, event_key, signature, Jsonb(payload)),
    ).fetchone()
    if inserted is None:
        existing = db.execute(
            "SELECT signature FROM character_custom_task_events WHERE character_id=%s AND event_key=%s",
            (character_id, event_key),
        ).fetchone()
        if existing["signature"] != signature:
            raise ValueError("Custom task event identity conflicts with stored facts")
        return {"replayed": True, "updated": [], "completed": []}
    updated, completed = [], []
    for key, rule in rules.items():
        delta = engine.increment(rule, payload)
        row = prior.get(key)
        if not delta or (row is not None and row["completed_at"] is not None):
            continue
        count = min(rule["target"], (row["count"] if row is not None else 0) + delta)
        done = count == rule["target"]
        db.execute(
            "INSERT INTO character_custom_task_progress "
            "(character_id,task_key,definition_signature,count,completed_at) "
            "VALUES (%s,%s,%s,%s,CASE WHEN %s THEN CURRENT_TIMESTAMP ELSE NULL END) "
            "ON CONFLICT(character_id,task_key) DO UPDATE SET count=EXCLUDED.count, "
            "completed_at=EXCLUDED.completed_at,updated_at=CURRENT_TIMESTAMP",
            (character_id, key, catalog.signature(rule), count, done),
        )
        updated.append(key)
        if done:
            completed.append(key)
            for index, reward in enumerate(rule["rewards"]):
                db.execute(
                    "INSERT INTO character_custom_task_reward_outbox "
                    "(character_id,task_key,reward_index,payload) VALUES (%s,%s,%s,%s)",
                    (character_id, key, index, Jsonb(reward)),
                )
    return {"replayed": False, "updated": updated, "completed": completed}


def snapshot(db, account_id, character_id, definitions=None, *, section=None, page=1):
    """Read an owned view, hiding disabled tasks without deleting earned history.

    This is server-owned data for an in-game presenter; it does not alter the
    installed native achievement/mission catalog or send a journal packet.
    """
    from . import external

    _owner(db, account_id, character_id, False)
    if external.enabled():
        return external.snapshot(db, character_id, section=section, page=page)
    rules = _definitions(db, definitions)
    rows = db.execute(
        "SELECT * FROM character_custom_task_progress WHERE character_id=%s",
        (character_id,),
    ).fetchall()
    prior = {row["task_key"]: row for row in rows}
    from .completion_rewards import notices

    reward_notices = notices(db)
    result = []
    for key, rule in rules.items():
        row = prior.get(key)
        if row is not None and row["definition_signature"] != catalog.signature(rule):
            raise ValueError(
                "Custom task key reused with different objective or rewards"
            )
        if not rule["enabled"]:
            continue
        result.append(
            {
                "key": key,
                "title": rule["title"],
                "description": rule["description"]
                + ("\n" + reward_notices[key] if key in reward_notices else ""),
                "target": rule["target"],
                "count": row["count"] if row is not None else 0,
                "completed": row is not None and row["completed_at"] is not None,
            }
        )
    return result
