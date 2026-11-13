"""Persist the four independently observed Rii introduction flags."""
from copy import deepcopy

from . import storage

TALKS = {10612: 10595, 10613: 10596, 10614: 10606, 10615: 10607}


def apply(db, character_id, state, definition, talk_objective, now_ms):
    """Record this NPC's flag and finish hidden 5154 after all four talks."""
    flag = TALKS[talk_objective]
    flags = definition.get("cjJ", [])
    if (
        definition.get("d") != 5154
        or definition.get("native_class") != "aJM"
        or definition.get("aqb") is not True
        or definition.get("isVisible") is not False
        or {item.get("d") for item in flags} != set(TALKS.values())
        or any(
            item.get("ckc") != "" or item.get("cke") != "" or item.get("ckf") != []
            for item in flags
        )
        or definition.get("cjK") != []
    ):
        raise ValueError("Rii introduction flags differ from native definition")
    after = deepcopy(state)
    objectives, completed = [], []
    if flag not in after["objectives"]:
        if not storage.record_event(
            db,
            character_id,
            f"rii-introduction-flag:{flag}",
            {"kind": "rii_introduction", "objective_id": flag},
        ):
            raise ValueError("Rii introduction receipt exists without its flag")
        after["objectives"] = sorted(set(after["objectives"]) | {flag})
        objectives.append(flag)
    if (
        set(TALKS.values()) <= set(after["objectives"])
        and 5154 not in after["completed"]
    ):
        if not storage.record_event(
            db,
            character_id,
            "rii-introduction-complete:5154",
            {"kind": "rii_introduction_complete", "quest_id": 5154},
        ):
            raise ValueError("Rii introduction receipt exists without completion")
        after["running"] = [
            identity for identity in after["running"] if identity != 5154
        ]
        after["tracking"] = [
            identity for identity in after["tracking"] if identity != 5154
        ]
        after["completed"] = sorted(set(after["completed"]) | {5154})
        after["completion_dates"]["5154"] = now_ms
        after["recent"] = (after["recent"] + [{"id": 5154, "date_ms": now_ms}])[-255:]
        completed.append(5154)
    return after, objectives, completed
