"""Start the Rii departure quest after its reconstructed guardian milestone.

The client objective names the Astrub Zaap, but the original activation event
was not recovered. Starting it after the guardian attempt is a reconstruction.
The caller supplies an authenticated guardian completion in its transaction.
"""
from copy import deepcopy

from . import mission_progress, storage


def activate(db, store, character, before, planned, *, now_ms):
    """Add quest 5161 to a newly completed guardian transition, once.

    The caller owns and authenticates the enclosing guardian transaction and
    persists/notifies the returned plan using the normal mission settlement.
    """
    if not isinstance(planned, tuple) or len(planned) != 4:
        raise ValueError("Invalid guardian completion plan")
    after, intents, objectives, completed = planned
    if type(now_ms) is not int or not 0 <= now_ms < 2**63:
        raise ValueError("Invalid departure activation time")
    if 5146 not in completed:
        return planned
    if (
        5146 not in before["running"]
        or 5146 in before["completed"]
        or 5146 not in after["completed"]
        or 10584 not in objectives
    ):
        raise ValueError("Departure requires a new guardian completion")
    if 5161 in after["running"] or 5161 in after["completed"]:
        return planned
    row = db.execute(
        "SELECT data FROM native_quest_metadata_definitions WHERE revision="
        "(SELECT revision FROM native_quest_metadata_releases ORDER BY imported_at DESC LIMIT 1) "
        "AND definition_id=%s",
        (5161,),
    ).fetchone()
    if row is None:
        raise ValueError("Missing Rii departure quest definition")
    definition = row["data"]["native"]
    if (
        definition.get("d") != 5161
        or definition.get("native_class") != "aJM"
        or definition.get("aqb") is not False
        or definition.get("cjI") != ""
        or definition.get("aHe") != "IsAchievementActive(5146)"
        or [objective.get("d") for objective in definition.get("cjJ", ())] != [10624]
    ):
        raise ValueError("Rii departure quest differs from native definition")
    if not storage.record_event(
        db,
        character["id"],
        "rii-departure-activation:5161",
        {"kind": "reconstructed_rii_departure_activation", "accepted_at_ms": now_ms},
    ):
        raise ValueError("Departure activation receipt exists without progress")
    candidate = deepcopy(after)
    candidate["running"] = sorted(set(candidate["running"]) | {5161})
    mission_progress.auto_track(candidate, 5161)
    return candidate, intents, objectives, completed
