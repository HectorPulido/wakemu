"""Transactional durable ingress, evaluator, definition management and read API."""

from wakfu_server.character_levels import MAX_CHARACTER_LEVEL
import hashlib
import secrets
from datetime import datetime, timezone
from psycopg.types.json import Jsonb
from .catalog import canonical, key, integer, validate_definition, semantic_signature
from .schedules import period_key
from .engine import increment


class ConflictError(ValueError):
    pass


def enqueue(db, account_id, character_id, event_key, payload, occurred_at=None):
    integer(account_id)
    integer(character_id)
    if type(event_key) is not str or not 1 <= len(event_key) <= 256:
        raise ValueError("Invalid event identity")
    if type(payload) is not dict or len(canonical(payload).encode()) > 65536:
        raise ValueError("Invalid or oversized event payload")
    key(payload.get("kind"))
    if payload["kind"] in {"original_monster_killed", "monster_seed_planted"}:
        from wakfu_server.custom_tasks.engine import event_payload, canonical_event_key

        payload = event_payload(payload)
        if event_key != canonical_event_key(payload):
            raise ValueError("Event identity does not match source fact")
    from .progression import ABSOLUTE_EVENTS, validate_fact

    if payload["kind"] in ABSOLUTE_EVENTS:
        validate_fact(db, account_id, payload)
    owner = db.execute(
        "SELECT id,level FROM characters WHERE id=%s AND account_id=%s AND deleted_at IS NULL",
        (character_id, account_id),
    ).fetchone()
    if owner is None:
        raise ValueError("Event character is not owned by account")
    if occurred_at is not None and occurred_at.tzinfo is None:
        raise ValueError("Event timestamp must include timezone")
    from . import assignments

    source_at = (
        occurred_at or db.execute("SELECT CURRENT_TIMESTAMP AS now").fetchone()["now"]
    )
    assignments.ensure_for_character(
        db, account_id, character_id, owner["level"], at=source_at
    )
    signature = hashlib.sha256(canonical(payload).encode()).hexdigest()
    db.execute("SELECT pg_advisory_xact_lock_shared(747117401)")
    candidates = db.execute(
        "SELECT DISTINCT d.key,d.definition,d.revision FROM objectives_definitions d "
        "CROSS JOIN LATERAL jsonb_array_elements(d.definition->'objectives') o "
        "WHERE (d.definition->>'enabled')::boolean AND o->>'event'=%s "
        "AND (NOT (o->'filters' ? 'map_id') OR o->'filters'->'map_id'=%s::jsonb "
        "OR o->'filters'->'map_id' @> %s::jsonb) ORDER BY d.key",
        (payload["kind"], Jsonb(payload.get("map_id")), Jsonb([payload.get("map_id")])),
    ).fetchall()
    candidates = [
        row
        for row in candidates
        if (
            assignments.is_assigned(
                db,
                account_id,
                row["key"],
                period_key(row["definition"]["schedule"], source_at),
            )
            if assignments.managed(row["definition"])
            else row["definition"].get("level_range", {"minimum": 1})["minimum"]
            <= owner["level"]
            <= row["definition"].get("level_range", {"maximum": MAX_CHARACTER_LEVEL})[
                "maximum"
            ]
        )
    ]
    definitions = [
        {"key": row["key"], "revision": row["revision"]}
        for row in candidates
        if any(increment(o, payload) for o in row["definition"]["objectives"])
    ]
    matched_keys = {reference["key"] for reference in definitions}
    policy_keys = {
        reward["policy_key"]
        for row in candidates
        if row["key"] in matched_keys
        for reward in row["definition"]["rewards"]
        if reward.get("kind") == "scaled"
    }
    policy_snapshot = {
        r["key"]: dict(r)
        for r in db.execute(
            "SELECT key,revision FROM objectives_reward_policies WHERE key=ANY(%s::text[])",
            (list(policy_keys),),
        ).fetchall()
    }
    row = db.execute(
        "INSERT INTO objectives_events(account_id,character_id,event_key,payload,signature,occurred_at,definitions,character_level,reward_policies) VALUES (%s,%s,%s,%s,%s,COALESCE(%s,CURRENT_TIMESTAMP),%s,%s,%s) ON CONFLICT(character_id,event_key) DO NOTHING RETURNING id",
        (
            account_id,
            character_id,
            event_key,
            Jsonb(payload),
            signature,
            occurred_at,
            Jsonb(definitions),
            owner["level"],
            Jsonb(policy_snapshot),
        ),
    ).fetchone()
    if row:
        db.execute(
            "SELECT pg_notify('wakemu_objectives_events',%s)", (str(character_id),)
        )
        return {"id": row["id"], "replayed": False}
    row = db.execute(
        "SELECT id,signature,occurred_at FROM objectives_events WHERE character_id=%s AND event_key=%s",
        (character_id, event_key),
    ).fetchone()
    if row["signature"] != signature or (
        occurred_at is not None and occurred_at != row["occurred_at"]
    ):
        raise ConflictError("Event identity conflicts with stored facts")
    return {"id": row["id"], "replayed": True}


def list_definitions(db):
    return db.execute("SELECT * FROM objectives_definitions ORDER BY key").fetchall()


def list_progress(db, character_id):
    integer(character_id)
    return db.execute(
        "SELECT %s AS character_id,p.definition_key,p.period_key,p.definition_revision,p.counters,"
        "p.completed_at,p.updated_at,(p.completed_at IS NOT NULL) AS rewards_reserved "
        "FROM objectives_account_progress p JOIN characters c ON c.account_id=p.account_id "
        "WHERE c.id=%s AND c.deleted_at IS NULL ORDER BY definition_key,period_key",
        (character_id, character_id),
    ).fetchall()


def put_definition(db, definition, expected_revision):
    value = validate_definition(definition)
    if value["scope"] != "account":
        raise ValueError("Objective progress must have account scope")
    if type(expected_revision) is not int or expected_revision < 0:
        raise ValueError("Expected revision must be nonnegative integer")
    # Serializes worker snapshots with all edits, including new definitions.
    db.execute("SELECT pg_advisory_xact_lock(747117401)")
    prior = db.execute(
        "SELECT * FROM objectives_definitions WHERE key=%s FOR UPDATE", (value["key"],)
    ).fetchone()
    if (prior["revision"] if prior else 0) != expected_revision:
        raise ConflictError("Definition revision has changed")
    if prior and semantic_signature(prior["definition"]) != semantic_signature(value):
        if (
            db.execute(
                "SELECT 1 FROM objectives_progress WHERE definition_key=%s LIMIT 1",
                (value["key"],),
            ).fetchone()
            or db.execute(
                "SELECT 1 FROM objectives_account_progress WHERE definition_key=%s LIMIT 1",
                (value["key"],),
            ).fetchone()
            or db.execute(
                "SELECT 1 FROM objectives_events WHERE processed_at IS NULL AND definitions @> %s::jsonb LIMIT 1",
                (Jsonb([{"key": value["key"]}]),),
            ).fetchone()
        ):
            raise ConflictError(
                "Earned objective semantics are immutable; create a new key"
            )
    definitions = {r["key"]: r["definition"] for r in list_definitions(db)}
    definitions[value["key"]] = value

    def walk(current, visiting):
        if current in visiting:
            raise ValueError("Cyclic objective prerequisites")
        for dependency in definitions[current].get("prerequisite_keys", []):
            if dependency not in definitions:
                raise ValueError("Unknown prerequisite")
            if definitions[current].get("scope", "character") != definitions[
                dependency
            ].get("scope", "character"):
                raise ValueError("Prerequisite scope must match objective scope")
            walk(dependency, visiting | {current})

    for definition_key in definitions:
        walk(definition_key, set())
    db.execute("SELECT pg_notify('wakemu_objectives_updates','0')")
    return db.execute(
        "INSERT INTO objectives_definitions(key,definition,revision) VALUES (%s,%s,1) ON CONFLICT(key) DO UPDATE SET definition=EXCLUDED.definition,revision=objectives_definitions.revision+1,updated_at=CURRENT_TIMESTAMP RETURNING *",
        (value["key"], Jsonb(value)),
    ).fetchone()


def reserve_rewards(db, character_id, definition, period, *, level=None, policies=None):
    from . import reward_policies

    existing = db.execute(
        "SELECT rewards_reserved FROM objectives_progress WHERE character_id=%s AND definition_key=%s AND period_key=%s",
        (character_id, definition["key"], period),
    ).fetchone()
    if existing and existing["rewards_reserved"]:
        return
    resolved = []
    provenance = []
    for reward in definition["rewards"]:
        if reward.get("kind") == "scaled":
            policy_key = reward["policy_key"]
            row = (policies or {}).get(policy_key)
            if policies is not None and row is None:
                raise ValueError("Scaled reward policy was unavailable at source time")
            if row is None:
                row = db.execute(
                    "SELECT key,policy,revision FROM objectives_reward_policies WHERE key=%s",
                    (policy_key,),
                ).fetchone()
            if row is None or level is None:
                raise ValueError("Scaled reward policy or frozen level is unavailable")
            if "policy" not in row:
                frozen = db.execute(
                    "SELECT policy FROM objectives_reward_policy_versions WHERE key=%s AND revision=%s",
                    (row["key"], row["revision"]),
                ).fetchone()
                if frozen is None:
                    raise ValueError("Frozen reward policy version is unavailable")
                row = {**row, "policy": frozen["policy"]}
            resolved.extend(reward_policies.expand(db, row, level))
            provenance.append(
                {"key": policy_key, "revision": row["revision"], "level": level}
            )
        else:
            resolved.append(reward)
    for index, reward in enumerate(resolved):
        if reward.get("kind") == "random_item":
            reward = {
                "aeV": 5,
                "ckl": [secrets.choice(reward["references"]), reward["quantity"]],
            }
        db.execute(
            "INSERT INTO objectives_rewards(character_id,definition_key,period_key,reward_index,payload,policy_snapshot) VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
            (
                character_id,
                definition["key"],
                period,
                index,
                Jsonb(reward),
                Jsonb(provenance),
            ),
        )

    db.execute(
        "UPDATE objectives_progress SET rewards_reserved=true WHERE character_id=%s AND definition_key=%s AND period_key=%s",
        (character_id, definition["key"], period),
    )


def _process_event(db, event, definitions):
    # Prerequisites must already be complete before this event is evaluated.
    # A parent completed below cannot unlock its child on the same source fact.
    account_completed_before = {
        (row["definition_key"], row["period_key"])
        for row in db.execute(
            "SELECT definition_key,period_key FROM objectives_account_progress WHERE account_id=%s "
            "AND completed_at IS NOT NULL AND completed_at<=%s",
            (event["account_id"], event["occurred_at"]),
        ).fetchall()
    }
    from . import onboarding, assignments

    account_source_admitted = None
    changed = 0
    for row in definitions:
        frozen = row.get("definition")
        if frozen is None:
            version = db.execute(
                "SELECT definition FROM objectives_definition_versions WHERE key=%s AND revision=%s",
                (row["key"], row["revision"]),
            ).fetchone()
            if version is None:
                raise ValueError("Frozen objective definition version is unavailable")
            frozen = version["definition"]
        rule = validate_definition(frozen)
        band = rule.get("level_range", {"minimum": 1, "maximum": MAX_CHARACTER_LEVEL})
        if not rule["enabled"]:
            continue
        period = period_key(rule["schedule"], event["occurred_at"])
        if period is None:
            continue
        if assignments.managed(rule):
            if not assignments.is_assigned(
                db, event["account_id"], rule["key"], period
            ):
                continue
        elif not band["minimum"] <= event["character_level"] <= band["maximum"]:
            continue
        # Scope is an account invariant, including frozen pre-migration facts.
        # Their objective/reward content stays immutable; only ownership changes.
        if account_source_admitted is None:
            account_source_admitted = onboarding.admit_source(db, event)
        if account_source_admitted:
            completed_before = {
                key
                for key, completed_period in account_completed_before
                if completed_period == "once" or completed_period == period
            }
            changed += onboarding.advance(
                db,
                event,
                rule,
                row["revision"],
                period,
                completed_before,
                reserve_rewards,
            )
    return changed


def process_batch(db, limit=100):
    integer(limit, 1000)
    # One evaluator lock preserves source ordering and prerequisite semantics.
    if not db.execute(
        "SELECT pg_try_advisory_xact_lock(747117402) AS locked"
    ).fetchone()["locked"]:
        return {"processed": 0, "failed": 0, "updated": 0}
    db.execute("SELECT pg_advisory_xact_lock_shared(747117401)")
    events = db.execute(
        "SELECT * FROM objectives_events WHERE processed_at IS NULL AND attempts<5 ORDER BY id LIMIT %s FOR UPDATE SKIP LOCKED",
        (limit,),
    ).fetchall()
    result = {"processed": 0, "failed": 0, "updated": 0}
    for event in events:
        try:
            with db.transaction():
                result["updated"] += _process_event(db, event, event["definitions"])
                from .rankings import record_attempt

                record_attempt(db, event)
                db.execute(
                    "UPDATE objectives_events SET processed_at=CURRENT_TIMESTAMP,error=NULL WHERE id=%s",
                    (event["id"],),
                )
            db.execute(
                "SELECT pg_notify('wakemu_objectives_updates',%s)",
                (str(event["character_id"]),),
            )
            result["processed"] += 1
        except Exception as exc:
            db.execute(
                "UPDATE objectives_events SET attempts=attempts+1,error=%s WHERE id=%s",
                (str(exc)[:2048], event["id"]),
            )
            result["failed"] += 1
    # Historical completed records may predate reward policy materialization.
    for row in db.execute(
        "SELECT p.character_id,p.definition_key,p.period_key,d.definition FROM objectives_progress p JOIN objectives_definitions d ON d.key=p.definition_key WHERE p.completed_at IS NOT NULL AND NOT p.rewards_reserved AND EXISTS (SELECT 1 FROM objectives_account_progress a JOIN characters c ON c.account_id=a.account_id WHERE c.id=p.character_id AND a.definition_key=p.definition_key AND a.period_key=p.period_key AND a.reward_character_id=p.character_id) AND jsonb_array_length(d.definition->'rewards')>0 AND NOT EXISTS (SELECT 1 FROM objectives_rewards r WHERE r.character_id=p.character_id AND r.definition_key=p.definition_key AND r.period_key=p.period_key) LIMIT 100"
    ).fetchall():
        reserve_rewards(
            db,
            row["character_id"],
            validate_definition(row["definition"]),
            row["period_key"],
        )
        db.execute(
            "SELECT pg_notify('wakemu_objectives_updates',%s)",
            (str(row["character_id"]),),
        )
    from .rankings import finalize_weeks

    try:
        with db.transaction():
            finalize_weeks(db)
        db.execute(
            "DELETE FROM objectives_service_state WHERE key='ranking_finalization_error'"
        )
    except Exception as exc:
        db.execute(
            "INSERT INTO objectives_service_state(key,value) VALUES('ranking_finalization_error',%s) ON CONFLICT(key) DO UPDATE SET value=EXCLUDED.value,updated_at=CURRENT_TIMESTAMP",
            (Jsonb({"error": str(exc)[:2048]}),),
        )
    return result
