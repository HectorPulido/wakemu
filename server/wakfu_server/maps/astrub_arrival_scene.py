"""Owned Rii fall and Astrub grandmother arrival from the official capture.

Scenario2536/22534 owns the rabbit visual. Its authenticated callback enters
map895 and starts this scenario2120 handshake, not the ordinary Astrub Zaap.
"""

from copy import deepcopy
import struct

SCENARIO_ID = 2120
MAP_ID = 895
INSTANCE_ID = 0
ENTRY_POSITION = (-8, -1, 18)
FINISH_POSITION = (-3, -4, 0)
QUEST_ID = 5568
DEPARTURE_QUEST_ID = 5161
DEPARTURE_OBJECTIVE_ID = 10624
GRANDMOTHER_REFERENCE_ID = 3257
GRANDMOTHER_POSITION = (0, -2, 0)
LOAD_EVENT = 17029
VIDEO_EVENT = 23936
CINEMATIC_EVENT = 17022
START_EVENT_KEY = "astrub-arrival:2120"
CALLBACK_PREFIX = "astrub-arrival-callback:"


def route():
    """The captured roof arrival, before the grandmother scene moves indoors."""
    return {
        "direction": 3,
        "destination": {
            "map_id": MAP_ID,
            "instance_id": INSTANCE_ID,
            **dict(zip(("x", "y", "z"), ENTRY_POSITION)),
        },
    }


def packet(event_id, *arguments):
    """Encode only the observed native presentation events and argument types."""
    if event_id not in (LOAD_EVENT, VIDEO_EVENT, CINEMATIC_EVENT):
        raise ValueError("Unqualified Astrub arrival event")
    if event_id == CINEMATIC_EVENT:
        if (
            len(arguments) != 1
            or type(arguments[0]) is not int
            or not -(2**63) <= arguments[0] < 0
        ):
            raise ValueError("Astrub arrival requires its real grandmother actor")
    elif arguments:
        raise ValueError("Astrub arrival event takes no arguments")
    return 13411, struct.pack(
        ">BiiB", 0, event_id, SCENARIO_ID, len(arguments)
    ) + b"".join(struct.pack(">q", value) for value in arguments)


def _definition(db, identity):
    row = db.execute(
        "SELECT data FROM native_quest_metadata_definitions WHERE revision="
        "(SELECT revision FROM native_quest_metadata_releases "
        "ORDER BY imported_at DESC LIMIT 1) AND definition_id=%s",
        (identity,),
    ).fetchone()
    native = None if row is None else row["data"]["native"]
    if (
        not isinstance(native, dict)
        or native.get("d") != identity
        or native.get("native_class") != "aJM"
        or native.get("aqb") is not False
    ):
        raise ValueError("Missing native Astrub arrival mission definition")
    return native


def _start_payload(character_id):
    return {"kind": "rii_fall_arrival", "character_id": character_id, "map_id": MAP_ID}


def _receipt(db, character_id, key):
    row = db.execute(
        "SELECT payload FROM character_achievement_events "
        "WHERE character_id=%s AND event_key=%s",
        (character_id, key),
    ).fetchone()
    return None if row is None else row["payload"]


def _on_map(character):
    return (character.get("map_id"), character.get("instance_id", 0)) == (
        MAP_ID,
        INSTANCE_ID,
    )


def enter(db, store, source, destination, *, recovery=False):
    """Settle departure and start5568 in the authenticated travel transaction.

    The caller owns account/session locks and the actual map transition. No
    ordinary map entry or public transport is authorized by this function.
    """
    from wakfu_server.achievements import (
        mission_dependencies,
        mission_progress,
        storage,
    )
    from wakfu_server.achievements.service import _owner

    if (
        source.get("id") != destination.get("id")
        or source.get("account_id") != destination.get("account_id")
        or (source.get("map_id"), source.get("instance_id", 0))
        != ((527, 0) if recovery else (1385, 0))
        or not _on_map(destination)
        or tuple(destination.get(k) for k in ("x", "y", "z")) != ENTRY_POSITION
    ):
        raise ValueError("Astrub arrival requires the authenticated Rii fall")
    _owner(db, destination)
    if not _rii_exit_receipts(db, destination["id"]):
        raise ValueError("Astrub arrival recovery lacks its authenticated Rii exit")
    before = storage.load_locked(db, destination["id"])
    previous = _receipt(db, destination["id"], START_EVENT_KEY)
    if previous is not None:
        if previous != _start_payload(destination["id"]):
            raise ValueError("Astrub arrival receipt differs")
        return []
    if 5278 not in before["completed"] or 10967 not in before["objectives"]:
        raise ValueError("Astrub arrival lacks its authenticated portal progress")
    definitions = {QUEST_ID: _definition(db, QUEST_ID)}
    now_ms = int(store.now().timestamp() * 1000)
    # The official capture leaves Rii before5161 is activated. The portal is
    # independent of the optional guardian/departure quest; settle it only
    # when it is already running, without inventing its activation or progress.
    planned = (deepcopy(before), [], [], [])
    if DEPARTURE_QUEST_ID in before["running"]:
        departure = _definition(db, DEPARTURE_QUEST_ID)
        definitions[DEPARTURE_QUEST_ID] = departure
        if [row.get("d") for row in departure.get("cjJ", ())] != [
            DEPARTURE_OBJECTIVE_ID
        ]:
            raise ValueError("Unexpected Rii departure mission definition")
        planned = mission_progress.advance_objective(
            before,
            departure,
            DEPARTURE_OBJECTIVE_ID,
            character=destination,
            store=store,
            now_ms=now_ms,
        )
    after, intents, objectives, completed = planned
    after = deepcopy(after)
    if QUEST_ID not in after["running"] and QUEST_ID not in after["completed"]:
        after["running"] = sorted(set(after["running"]) | {QUEST_ID})
        mission_progress.auto_track(after, QUEST_ID)
        mission_progress.seed_counters(after, definitions[QUEST_ID])
    if not storage.record_event(
        db, destination["id"], START_EVENT_KEY, _start_payload(destination["id"])
    ):
        raise ValueError("Astrub arrival receipt raced")
    result = mission_dependencies.settle(
        db,
        store,
        destination,
        before,
        (after, intents, objectives, completed),
        definitions,
        (),
        now_ms=now_ms,
    )
    return [*result["packets"], packet(LOAD_EVENT)]


def pending(db, character):
    """Only resume a scene whose owned arrival transaction committed."""
    return (
        _on_map(character)
        and _receipt(db, character["id"], START_EVENT_KEY)
        == _start_payload(character["id"])
        and _receipt(db, character["id"], CALLBACK_PREFIX + str(CINEMATIC_EVENT))
        is None
    )


def login_packets(db, character):
    return (packet(LOAD_EVENT),) if pending(db, character) else ()


def _rii_exit_receipts(db, character_id):
    from wakfu_server import rii_zaap_scene

    return _receipt(
        db, character_id, rii_zaap_scene.START_EVENT_KEY
    ) == rii_zaap_scene._start_payload(character_id) and _receipt(
        db, character_id, rii_zaap_scene.CALLBACK_EVENT_KEY
    ) == {
        "kind": "rii_zaap_scene_callback",
        "character_id": character_id,
        "scenario_event": 22534,
    }


def recover_login(store, account_id, generation, character):
    """Catch up only the authenticated legacy fall that omitted mission5568.

    An ordinary Astrub visit, completed arrival or existing mission is never
    moved or reset. The compatibility move and mission activation commit once.
    """
    from wakfu_server.achievements import storage

    if (character.get("map_id"), character.get("instance_id", 0)) != (527, 0):
        return None
    with store.connection() as db:
        db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account_id,))
        store.lock_character(db, account_id, generation, character["id"], selected=True)
        current = store.character(account_id, character["id"], db)
        if (current.get("map_id"), current.get("instance_id", 0)) != (527, 0):
            return None
        state = storage.load_locked(db, current["id"])
        if (
            not _rii_exit_receipts(db, current["id"])
            or 5278 not in state["completed"]
            or 10967 not in state["objectives"]
            or QUEST_ID in state["running"]
            or QUEST_ID in state["completed"]
            or _receipt(db, current["id"], START_EVENT_KEY) is not None
        ):
            return None
        saved = store.transition_map_in_transaction(
            db, account_id, generation, current["id"], current, route()["destination"]
        )
        packets = enter(db, store, current, saved, recovery=True)
        saved = store.character(account_id, current["id"], db)
    return saved, tuple(packets)


def grandmother_actor(db):
    """Resolve the enabled scene actor that the native Lua hides and restores."""
    rows = db.execute(
        "SELECT actor_id FROM world_dialogue_npcs WHERE enabled AND map_id=%s "
        "AND instance_id=%s AND reference_id=%s AND x=%s AND y=%s AND z=%s "
        "UNION SELECT actor_id FROM world_native_npc_placements WHERE enabled "
        "AND map_id=%s AND instance_id=%s AND reference_id=%s AND x=%s AND y=%s AND z=%s",
        (MAP_ID, INSTANCE_ID, GRANDMOTHER_REFERENCE_ID, *GRANDMOTHER_POSITION) * 2,
    ).fetchall()
    if (
        len(rows) != 1
        or type(rows[0]["actor_id"]) is not int
        or rows[0]["actor_id"] >= 0
    ):
        raise ValueError("Astrub grandmother actor is not uniquely published")
    return rows[0]["actor_id"]


def callback(
    store,
    account_id,
    generation,
    character,
    body,
    *,
    pending_character_id,
    in_combat=False,
    expected_event=None,
):
    """Advance only this owner's captured load/video/cinematic handshake."""
    from wakfu_server.achievements import storage

    if not isinstance(body, bytes) or len(body) != 4:
        raise ValueError("Invalid Astrub arrival callback")
    event_id = struct.unpack(">i", body)[0]
    if expected_event is not None and event_id != expected_event:
        raise ValueError("Astrub arrival callback phase is not pending")
    if (
        event_id not in (LOAD_EVENT, VIDEO_EVENT, CINEMATIC_EVENT)
        or pending_character_id != character.get("id")
        or not _on_map(character)
        or in_combat
    ):
        raise ValueError("Astrub arrival callback is not pending")
    with store.connection() as db:
        db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account_id,))
        store.lock_character(db, account_id, generation, character["id"], selected=True)
        current = store.character(account_id, character["id"], db)
        if not _on_map(current) or _receipt(
            db, current["id"], START_EVENT_KEY
        ) != _start_payload(current["id"]):
            raise ValueError("Astrub arrival callback lacks its owned start")
        done_key = CALLBACK_PREFIX + str(CINEMATIC_EVENT)
        if _receipt(db, current["id"], done_key) is not None:
            return {"character": current, "packets": (), "finished": True}
        if event_id != LOAD_EVENT:
            prerequisite = LOAD_EVENT if event_id == VIDEO_EVENT else VIDEO_EVENT
            if _receipt(db, current["id"], CALLBACK_PREFIX + str(prerequisite)) is None:
                raise ValueError("Astrub arrival callback is out of order")
        key = CALLBACK_PREFIX + str(event_id)
        payload = {
            "kind": "astrub_arrival_callback",
            "character_id": current["id"],
            "event_id": event_id,
        }
        previous = _receipt(db, current["id"], key)
        if previous is None:
            if not storage.record_event(db, current["id"], key, payload):
                raise ValueError("Astrub arrival callback receipt raced")
        elif previous != payload:
            raise ValueError("Astrub arrival callback receipt differs")
        finished = event_id == CINEMATIC_EVENT
        if finished:
            x, y, z = FINISH_POSITION
            result = db.execute(
                "UPDATE characters SET x=%s,y=%s,z=%s "
                "WHERE id=%s AND account_id=%s AND map_id=%s AND instance_id=%s",
                (x, y, z, current["id"], account_id, MAP_ID, INSTANCE_ID),
            )
            if result.rowcount != 1:
                raise ValueError("Astrub arrival owner position could not be persisted")
            current.update(x=x, y=y, z=z)
            packets = ((13259, struct.pack(">qiihBB", current["id"], x, y, z, 0, 0)),)
        elif (
            event_id == LOAD_EVENT
            and _receipt(db, current["id"], CALLBACK_PREFIX + str(VIDEO_EVENT)) is None
        ):
            packets = (packet(VIDEO_EVENT),)
        else:
            packets = (packet(CINEMATIC_EVENT, grandmother_actor(db)),)
    return {"character": current, "packets": packets, "finished": finished}
