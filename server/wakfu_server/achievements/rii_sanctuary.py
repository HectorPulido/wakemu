"""Progress the active Rii sanctuary quest on its verified entrance route."""
from copy import deepcopy

from . import mission_progress, storage, wire


def enter(db, store, source, destination, route):
    if (
        source.get("map_id"),
        source.get("instance_id"),
        destination.get("map_id"),
        destination.get("instance_id"),
        route.get("interactive_element_id"),
        route.get("destination_id"),
    ) != (1385, 0, 1387, 0, 34619, 4560):
        return []
    if (source.get("id"), source.get("account_id")) != (
        destination.get("id"),
        destination.get("account_id"),
    ):
        raise ValueError("Sanctuary travel changed character identity")
    level = destination.get("level")
    if type(level) is not int or level < 6:
        return []
    before = storage.load_locked(db, destination["id"])
    if 5146 in before["completed"] or 10582 in before["objectives"]:
        return []
    if 5146 not in before["running"]:
        return []
    row = db.execute(
        "SELECT data FROM native_quest_metadata_definitions WHERE revision="
        "(SELECT revision FROM native_quest_metadata_releases ORDER BY imported_at DESC LIMIT 1) "
        "AND definition_id=%s",
        (5146,),
    ).fetchone()
    if row is None:
        raise ValueError("Missing sanctuary mission definition")
    definition = row["data"]["native"]
    if (
        definition.get("d") != 5146
        or definition.get("native_class") != "aJM"
        or definition.get("aqb") is not False
        or definition.get("cjI") != ""
        or [item.get("d") for item in definition.get("cjJ", ())]
        != [10582, 10583, 10584]
    ):
        raise ValueError("Sanctuary mission differs from native definition")
    candidate = deepcopy(before)
    now_ms = int(store.now().timestamp() * 1000)
    after, intents, objectives, completed = mission_progress.advance_objective(
        candidate, definition, 10582, character=destination, store=store, now_ms=now_ms
    )
    if intents or completed or objectives != [10582]:
        raise ValueError("Unexpected sanctuary entry transition")
    if not storage.record_event(
        db,
        destination["id"],
        "rii-sanctuary-entry:10582",
        {"kind": "reconstructed_rii_sanctuary_entry", "accepted_at_ms": now_ms},
    ):
        raise ValueError("Sanctuary receipt exists without progress")
    storage.store(db, destination["id"], after)
    return wire.changes(
        destination["id"],
        before,
        after,
        objectives,
        completed,
        now_ms,
        definitions={5146: definition},
    )
