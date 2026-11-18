"""Mission facts derived from an already authorized native Zaap journey.

The installed Rii quest describes this journey, but the original server's
precise trigger was not recovered.  This is an explicit local reconstruction.
The caller owns the same transaction as the map transition and must only pass a
route returned by native_transports.resolve for this character.
"""

from . import mission_progress, storage, wire


def on_native_transport(db, store, source, destination, route):
    """Complete an active Rii departure quest after Rii-to-Astrub Zaap travel."""
    from wakfu_server import native_transports
    from .service import _owner, drain_rewards

    if source.get("id") != destination.get("id") or source.get(
        "account_id"
    ) != destination.get("account_id"):
        raise ValueError("Native transport changed character identity")
    if (
        source.get("map_id"),
        source.get("instance_id"),
        destination.get("map_id"),
        destination.get("instance_id"),
    ) != (1385, 0, 527, 0):
        return []
    start_id, end_id = route.get("source_id"), route.get("destination_id")
    start = native_transports.ZAAPS.get(start_id)
    end = native_transports.ZAAPS.get(end_id)
    start_object = native_transports.OBJECTS.get(start_id)
    end_object = native_transports.OBJECTS.get(end_id)
    if (
        start is None
        or end is None
        or start_object is None
        or end_object is None
        or start_object["map_id"] != 1385
        or end_object["map_id"] != 527
        or route.get("destination")
        != {key: destination[key] for key in ("map_id", "instance_id", "x", "y", "z")}
    ):
        return []
    _owner(db, destination)
    before = storage.load_locked(db, destination["id"])
    if 5161 not in before["running"]:
        return []
    row = db.execute(
        "SELECT data FROM native_quest_metadata_definitions WHERE revision="
        "(SELECT revision FROM native_quest_metadata_releases ORDER BY imported_at DESC LIMIT 1) "
        "AND definition_id=%s",
        (5161,),
    ).fetchone()
    if row is None:
        raise ValueError("Missing Rii departure mission definition")
    definition = row["data"]["native"]
    if definition.get("d") != 5161 or {r["d"] for r in definition.get("cjJ", ())} != {
        10624
    }:
        raise ValueError("Unexpected Rii departure mission definition")
    now_ms = int(store.now().timestamp() * 1000)
    after, intents, objectives, completed = mission_progress.advance_objective(
        before, definition, 10624, character=destination, store=store, now_ms=now_ms
    )
    if not objectives:
        return []
    fact = {
        "kind": "native_zaap_mission",
        "quest_id": 5161,
        "objective_id": 10624,
        "source_id": start_id,
        "destination_id": end_id,
    }
    if not storage.record_event(
        db, destination["id"], "native-zaap-mission:5161:10624", fact
    ):
        raise ValueError("Transport mission receipt exists without progress")
    for identity, reward in intents:
        storage.claim_reward(
            db, destination["id"], identity, "once", reward["d"], reward
        )
    storage.store(db, destination["id"], after)
    packets = wire.changes(
        destination["id"], before, after, objectives, completed, now_ms
    )
    packets.extend(drain_rewards(db, store, destination))
    if completed:
        from . import mission_toolkit

        packets.extend(
            mission_toolkit.settle_completions(db, store, destination, completed)
        )
    return packets
