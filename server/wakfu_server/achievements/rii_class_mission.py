"""Reconstructed Rii class-change reminder tied to the character's real level.

The client describes 5144 as a level-30 reminder, not an instruction to
change class. Starting it on arrival is a local reconstruction; no native
server activation effect has been recovered.
"""
from copy import deepcopy

from . import mission_progress, storage, wire


def _definition(db):
    row = db.execute(
        "SELECT data FROM native_quest_metadata_definitions WHERE revision="
        "(SELECT revision FROM native_quest_metadata_releases ORDER BY imported_at DESC LIMIT 1) "
        "AND definition_id=%s",
        (5144,),
    ).fetchone()
    if row is None:
        raise ValueError("Missing Rii class reminder definition")
    native = row["data"]["native"]
    objectives = native.get("cjJ", [])
    if (
        native.get("d") != 5144
        or native.get("native_class") != "aJM"
        or native.get("aqb") is not True
        or native.get("isVisible") is not True
        or native.get("aHe") != "GetRealLevel() < 30"
        or native.get("cjI") != ""
        or native.get("bwX") != 5160
        or native.get("cjU") != 0
        or native.get("getDuration") != 0
        or native.get("cjK") != []
        or len(objectives) != 1
        or objectives[0].get("d") != 10577
        or objectives[0].get("ckc") != ""
        or objectives[0].get("cke") != ""
        or objectives[0].get("ckf") != []
    ):
        raise ValueError("Rii class reminder differs from native definition")
    return native


def start(db, store, character, *, previous_map):
    """Start and track the reminder only on a qualified arrival below level 30."""
    if previous_map is not None and (
        type(previous_map) is not int or previous_map <= 0
    ):
        raise ValueError("Invalid Rii arrival origin")
    if previous_map == 1385 or (
        character.get("map_id"),
        character.get("instance_id"),
    ) != (1385, 0):
        return []
    level = character.get("level")
    if type(level) is not int or level <= 0:
        raise ValueError("Invalid real level for Rii class reminder")
    if level >= 30:
        return []
    before = storage.load_locked(db, character["id"])
    if 5144 in before["running"] or 5144 in before["completed"]:
        return []
    _definition(db)
    now_ms = int(store.now().timestamp() * 1000)
    if not storage.record_event(
        db,
        character["id"],
        "rii-class-reminder:start",
        {"kind": "reconstructed_rii_class_reminder", "accepted_at_ms": now_ms},
    ):
        raise ValueError("Rii class reminder receipt exists without progress")
    after = deepcopy(before)
    after["running"] = sorted(set(after["running"]) | {5144})
    mission_progress.auto_track(after, 5144)
    storage.store(db, character["id"], after)
    return wire.changes(character["id"], before, after, [], [], now_ms)


def reached_level(db, store, character, level):
    """Complete a running reminder after an authoritative real-level update."""
    if type(level) is not int or level <= 0:
        raise ValueError("Invalid real level for Rii class reminder")
    if level < 30:
        return []
    before = storage.load_locked(db, character["id"])
    if 5144 not in before["running"] or 5144 in before["completed"]:
        return []
    _definition(db)
    now_ms = int(store.now().timestamp() * 1000)
    if not storage.record_event(
        db,
        character["id"],
        "rii-class-reminder:level30",
        {"kind": "rii_class_reminder_level_reached", "level": level},
    ):
        raise ValueError(
            "Rii class reminder completion receipt exists without progress"
        )
    after = deepcopy(before)
    after["running"].remove(5144)
    after["tracking"] = [i for i in after["tracking"] if i != 5144]
    after["objectives"] = sorted(set(after["objectives"]) | {10577})
    after["completed"] = sorted(set(after["completed"]) | {5144})
    after["completion_dates"]["5144"] = now_ms
    after["recent"] = (after["recent"] + [{"id": 5144, "date_ms": now_ms}])[-255:]
    storage.store(db, character["id"], after)
    return wire.changes(character["id"], before, after, [10577], [5144], now_ms)
