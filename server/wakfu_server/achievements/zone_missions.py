"""Mission activation on an authenticated Rii arrival.

An official session started both 5160 and 5146 at the island transition.
"""
from copy import deepcopy

from . import mission_progress, storage, wire


def enter_rii(db, store, character, *, previous_map):
    """Start Rii's nonperiodic introductory mission after a qualified entry.

    Caller must own the transaction and validate session, ownership and the
    committed map transition. A reconnect within Rii is not an entry. Existing
    progress and rewards are never altered by repeat visits.
    """
    if previous_map is not None and (
        type(previous_map) is not int or previous_map <= 0
    ):
        raise ValueError("Invalid previous map")
    if previous_map == 1385 or (character["map_id"], character["instance_id"]) != (
        1385,
        0,
    ):
        return []
    before = storage.load_locked(db, character["id"])
    missing = [
        identity
        for identity in (5160, 5146)
        if identity not in before["running"] and identity not in before["completed"]
    ]
    if not missing:
        return []
    definitions = {}
    for identity in missing:
        row = db.execute(
            "SELECT data FROM native_quest_metadata_definitions WHERE revision="
            "(SELECT revision FROM native_quest_metadata_releases ORDER BY imported_at DESC LIMIT 1) "
            "AND definition_id=%s",
            (identity,),
        ).fetchone()
        if not row:
            raise ValueError("Missing Rii starting mission definition")
        native = row["data"]["native"]
        if (
            native.get("d") != identity
            or native.get("native_class") != "aJM"
            or native.get("aqb") is not False
            or native.get("cjI") != ""
            or native.get("cjU") != 0
            or native.get("getDuration") != 0
        ):
            raise ValueError("Rii starting mission definition does not match policy")
        definitions[identity] = native
    accepted_at_ms = int(store.now().timestamp() * 1000)
    after = deepcopy(before)
    for identity in missing:
        if not storage.record_event(
            db,
            character["id"],
            f"zone-entry-mission:{identity}",
            {
                "kind": "zone_entry_mission",
                "definition_id": identity,
                "map_id": 1385,
                "instance_id": 0,
                "accepted_at_ms": accepted_at_ms,
            },
        ):
            raise ValueError("Rii activation receipt exists without mission state")
        after["running"] = sorted(set(after["running"]) | {identity})
        mission_progress.auto_track(after, identity)
    storage.store(db, character["id"], after)
    return wire.changes(
        character["id"], before, after, [], [], accepted_at_ms, definitions=definitions
    )
