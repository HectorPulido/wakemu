"""Retry room hydration without undoing an already earned dungeon victory."""
import json
import time

from psycopg.errors import DeadlockDetected, LockNotAvailable, SerializationFailure


def prepare(db, groups, *, instance_id, fight_id, map_id, geometry_provider, now=None):
    """Hydrate the committed frontier before publishing doors or automatic travel.

    The caller may share the reward transaction: only hydration runs inside a
    savepoint. Its durable retry journal belongs to the existing victory receipt,
    so reconnect and restart use the same idempotent room registration path.
    Invalid ownership/results and unrelated database errors are never repaired
    by manufacturing a victory, route, group or reward.
    """
    from wakfu_server import dungeon_runtime

    progress = db.execute(
        "SELECT current_room,status,revision FROM dungeon_room_runs "
        "WHERE instance_id=%s FOR UPDATE",
        (instance_id,),
    ).fetchone()
    encounter = db.execute(
        "SELECT status,encounter_scope,result,result_revision FROM dungeon_room_encounters "
        "WHERE instance_id=%s AND fight_id=%s FOR UPDATE",
        (instance_id, fight_id),
    ).fetchone()
    if (
        progress is None
        or encounter is None
        or encounter["status"] != "victory"
        or encounter.get("encounter_scope", "main") != "main"
        or encounter["result_revision"] != progress["revision"]
    ):
        return dict(state="obsolete", ready=False)
    result = encounter["result"]
    if (
        result.get("victory") is not True
        or result.get("current_room") != progress["current_room"]
        or result.get("completed") != (progress["status"] == "completed")
        or progress["status"] not in ("active", "completed")
    ):
        raise ValueError("Dungeon room hydration lacks its authoritative victory")
    prior = result.get("room_hydration", {})
    if prior.get("state") == "ready":
        return dict(state="ready", ready=True, replay=True)
    now = time.time() if now is None else now
    if now < prior.get("next_retry", 0):
        return dict(
            state="deferred",
            ready=False,
            next_retry=prior["next_retry"],
            recovery_required=prior.get("recovery_required", False),
        )
    attempts = prior.get("attempts", 0) + 1
    try:
        with db.transaction():
            dungeon_runtime.ensure_current_room(
                db,
                groups,
                instance_id,
                None
                if progress["status"] == "completed"
                else geometry_provider(map_id),
            )
    except (
        ValueError,
        DeadlockDetected,
        LockNotAvailable,
        SerializationFailure,
    ) as error:
        reason = str(error)[:512]
        same_failure = (
            prior.get("error_type") == type(error).__name__
            and prior.get("reason") == reason
        )
        failure_attempts = (prior.get("failure_attempts", 0) if same_failure else 0) + 1
        journal = dict(
            state="pending",
            attempts=attempts,
            last_attempt=now,
            next_retry=now + min(60, 2 ** min(attempts, 6)),
            failure_attempts=failure_attempts,
            recovery_required=isinstance(error, ValueError) and failure_attempts >= 3,
            error_type=type(error).__name__,
            reason=reason,
        )
    else:
        journal = dict(state="ready", attempts=attempts, last_attempt=now)
    db.execute(
        "UPDATE dungeon_room_encounters SET result=result || "
        "jsonb_build_object('room_hydration',%s::jsonb) "
        "WHERE instance_id=%s AND fight_id=%s AND result_revision=%s",
        (json.dumps(journal), instance_id, fight_id, progress["revision"]),
    )
    return dict(journal, ready=journal["state"] == "ready", replay=False)
