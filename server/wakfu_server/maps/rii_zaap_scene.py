"""Owned Rii portal scene for the native 22534 leave-Rii event."""

from copy import deepcopy
import struct

MAP_ID = 1385
INSTANCE_ID = 0
ELEMENT_ID = 34719
ACTION_ID = 5
SCENARIO_ID = 2536
EVENT_ID = 22534
HIDDEN_QUEST_ID = 5278
OBJECTIVE_ID = 10967

# Official 2026-11-12 object descriptor and activation path. The request can
# arrive at the captured approach tile or once movement has reached a trigger.
APPROACH_POSITION = (2, -11, 1)
TRIGGER_CELLS = frozenset({(2, -15, 1), (3, -15, 1), (4, -15, 1)})
AUTHORIZED_POSITIONS = TRIGGER_CELLS | {APPROACH_POSITION}
SCENE_POSITION = (3, -18, 4)
SCENE_DIRECTION = 3
SCENE_MODE_ID = -1

START_EVENT_KEY = "rii-zaap-scene:22534"
CALLBACK_EVENT_KEY = "rii-zaap-scene-callback:22534"
# Captured server cwN update for the exact map object after event22534 starts.
ELEMENT_STATE_PAYLOAD = bytes.fromhex(
    "000000000000879f001301020000000602000101010000000000000000"
)


def departure_route():
    """Return the captured fall into the grandmother's house."""
    from wakfu_server import astrub_arrival_scene

    return astrub_arrival_scene.route()


def pending_scene(db, character):
    """Return true only for an authenticated start lacking its callback receipt."""
    if (
        not isinstance(character, dict)
        or (character.get("map_id"), character.get("instance_id", 0))
        != (MAP_ID, INSTANCE_ID)
        or character.get("id") is None
    ):
        return False
    rows = db.execute(
        "SELECT event_key,payload FROM character_achievement_events "
        "WHERE character_id=%s AND event_key=ANY(%s)",
        (character["id"], [START_EVENT_KEY, CALLBACK_EVENT_KEY]),
    ).fetchall()
    events = {row["event_key"]: row["payload"] for row in rows}
    return (
        events.get(START_EVENT_KEY) == _start_payload(character["id"])
        and CALLBACK_EVENT_KEY not in events
    )


def login_packets(db, character):
    """Resume only the unacknowledged scene; never replay mission progress."""
    if not pending_scene(db, character):
        return ()
    from wakfu_server import rii_scenario

    return (
        rii_scenario.packet(rii_scenario.ZAAP_LEAVE),
        (12344, ELEMENT_STATE_PAYLOAD),
    )


def _start_payload(character_id):
    return {
        "kind": "rii_zaap_scene",
        "character_id": character_id,
        "element_id": ELEMENT_ID,
        "action_id": ACTION_ID,
        "scenario_event": EVENT_ID,
        "objective_id": OBJECTIVE_ID,
        "quest_id": HIDDEN_QUEST_ID,
    }


def handles_activation(character, body):
    """Recognize this one map-scoped native object request for gateway routing."""
    if not isinstance(character, dict) or not isinstance(body, bytes) or len(body) < 8:
        return False
    return (character.get("map_id"), character.get("instance_id", 0)) == (
        MAP_ID,
        INSTANCE_ID,
    ) and struct.unpack_from(">q", body)[0] == ELEMENT_ID


def _parse_activation(body):
    if not isinstance(body, bytes) or len(body) != 12:
        raise ValueError("Invalid Rii portal activation")
    element, action, padding = struct.unpack(">qHH", body)
    if (element, action, padding) != (ELEMENT_ID, ACTION_ID, 0):
        raise ValueError("Rii portal activation differs from the native interaction")


def _authorized_position(character, *, approved_positions=()):
    if not isinstance(character, dict) or (
        character.get("map_id"),
        character.get("instance_id", 0),
    ) != (MAP_ID, INSTANCE_ID):
        raise ValueError("Rii portal activation is outside its captured trigger")
    position = tuple(character.get(key) for key in ("x", "y", "z"))
    if position in AUTHORIZED_POSITIONS:
        return
    # Exploration persists the approved route's destination before the native
    # client finishes walking it. A position trigger can therefore fire while
    # the character's stored endpoint is already beyond its footprint. Accept
    # only this session's validated route, including its current endpoint.
    if (
        not isinstance(approved_positions, (tuple, list, set, frozenset))
        or not 1 <= len(approved_positions) <= 257
        or any(
            not isinstance(cell, tuple)
            or len(cell) != 3
            or any(type(value) is not int for value in cell)
            for cell in approved_positions
        )
    ):
        raise ValueError("Rii portal activation is outside its captured trigger")
    approved = frozenset(approved_positions)
    if position not in approved or not approved.intersection(TRIGGER_CELLS):
        raise ValueError("Rii portal activation is outside its captured trigger")


def _validate_hidden_definition(definition):
    if (
        not isinstance(definition, dict)
        or definition.get("d") != HIDDEN_QUEST_ID
        or definition.get("native_class") != "aJM"
        or definition.get("aqb") is not True
        or definition.get("isVisible") is not False
        or definition.get("cjI") != ""
        or definition.get("cjU") != 0
        or definition.get("getDuration") != 0
        or definition.get("cjK") != []
    ):
        raise ValueError("Hidden Rii portal quest differs from native metadata")
    objectives = definition.get("cjJ")
    if (
        not isinstance(objectives, list)
        or len(objectives) != 1
        or objectives[0].get("d") != OBJECTIVE_ID
        or objectives[0].get("native_class") != "aJN"
        or objectives[0].get("ckb") is not True
        or objectives[0].get("ckc") != ""
        or objectives[0].get("cke") != ""
        or objectives[0].get("ckd") != []
        or objectives[0].get("ckf") != []
    ):
        raise ValueError("Hidden Rii portal objective differs from native metadata")


def _complete_hidden_step(state, definition, now_ms):
    """Apply the captured hidden fact without activating/tracking its quest."""
    _validate_hidden_definition(definition)
    if type(now_ms) is not int or now_ms < 0:
        raise ValueError("Invalid Rii portal completion time")
    done = OBJECTIVE_ID in state["objectives"]
    complete = HIDDEN_QUEST_ID in state["completed"]
    if done != complete:
        raise ValueError("Rii portal progress is only partially persisted")
    if done:
        return deepcopy(state), [], []
    after = deepcopy(state)
    after["objectives"] = sorted(set(after["objectives"]) | {OBJECTIVE_ID})
    after["running"] = [value for value in after["running"] if value != HIDDEN_QUEST_ID]
    after["tracking"] = [
        value for value in after["tracking"] if value != HIDDEN_QUEST_ID
    ]
    after["completed"] = sorted(set(after["completed"]) | {HIDDEN_QUEST_ID})
    after["completion_dates"][str(HIDDEN_QUEST_ID)] = now_ms
    after["recent"] = (after["recent"] + [{"id": HIDDEN_QUEST_ID, "date_ms": now_ms}])[
        -255:
    ]
    return after, [OBJECTIVE_ID], [HIDDEN_QUEST_ID]


def callback_id(body):
    if not isinstance(body, bytes) or len(body) != 4:
        raise ValueError("Invalid Rii portal scenario callback")
    return struct.unpack(">i", body)[0]


def _persist_position(db, character, position):
    x, y, z = position
    result = db.execute(
        "UPDATE characters SET x=%s,y=%s,z=%s WHERE id=%s AND account_id=%s "
        "AND map_id=%s AND instance_id=%s",
        (
            x,
            y,
            z,
            character["id"],
            character["account_id"],
            MAP_ID,
            INSTANCE_ID,
        ),
    )
    if result.rowcount != 1:
        raise ValueError("Rii portal owner position could not be persisted")
    character.update(x=x, y=y, z=z)


def begin(store, account_id, generation, character, body, *, approved_positions=()):
    """Commit the captured hidden objective and launch scene22534 once."""
    _parse_activation(body)
    _authorized_position(character, approved_positions=approved_positions)
    from wakfu_server.achievements import storage, wire
    from wakfu_server import rii_scenario

    with store.connection() as db:
        db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account_id,))
        store.lock_character(db, account_id, generation, character["id"], selected=True)
        current = store.character(account_id, character["id"], db)
        _authorized_position(current, approved_positions=approved_positions)
        if tuple(current[key] for key in ("x", "y", "z")) != tuple(
            character[key] for key in ("x", "y", "z")
        ):
            raise ValueError("Rii portal position changed during activation")

        before = storage.load_locked(db, current["id"])
        definition_row = db.execute(
            "SELECT data FROM native_quest_metadata_definitions WHERE revision="
            "(SELECT revision FROM native_quest_metadata_releases "
            "ORDER BY imported_at DESC LIMIT 1) AND definition_id=%s",
            (HIDDEN_QUEST_ID,),
        ).fetchone()
        if definition_row is None:
            raise ValueError("Missing native hidden Rii portal quest")
        definition = definition_row["data"]["native"]
        now_ms = int(store.now().timestamp() * 1000)
        after, objectives, completed = _complete_hidden_step(before, definition, now_ms)

        existing = db.execute(
            "SELECT payload FROM character_achievement_events "
            "WHERE character_id=%s AND event_key=%s",
            (current["id"], START_EVENT_KEY),
        ).fetchone()
        payload = _start_payload(current["id"])
        if existing is not None:
            if existing["payload"] != payload:
                raise ValueError("Rii portal activation receipt differs")
            if (
                OBJECTIVE_ID not in after["objectives"]
                or HIDDEN_QUEST_ID not in after["completed"]
            ):
                raise ValueError("Rii portal receipt exists without hidden progress")
            return {"character": current, "packets": (), "started": False}

        if not objectives or not completed:
            raise ValueError(
                "Rii portal progress exists without its deduplication receipt"
            )
        if not storage.record_event(db, current["id"], START_EVENT_KEY, payload):
            raise ValueError("Rii portal activation receipt raced without progress")
        storage.store(db, current["id"], after)
        _persist_position(db, current, SCENE_POSITION)
        packets = wire.changes(
            current["id"],
            before,
            after,
            objectives,
            completed,
            now_ms,
            definitions={HIDDEN_QUEST_ID: definition},
        )
        packets.insert(
            0,
            (
                13530,
                struct.pack(
                    ">qiihBi",
                    current["id"],
                    *SCENE_POSITION,
                    SCENE_DIRECTION,
                    SCENE_MODE_ID,
                ),
            ),
        )
        packets.append(rii_scenario.packet(rii_scenario.ZAAP_LEAVE))
        packets.append((12344, ELEMENT_STATE_PAYLOAD))
    return {"character": current, "packets": tuple(packets), "started": True}


def finish(
    store,
    account_id,
    generation,
    character,
    body,
    *,
    route=None,
    pending_character_id,
    in_combat=False,
):
    """Settle the captured native Zaap exit after its cinematic callback.

    The scripted callback authorizes the installed Zaap route without fabricating
    a character position at the source object. ``mission_transport`` owns the
    map change and applies the native transport mission in the same transaction.
    """
    if (
        callback_id(body) != EVENT_ID
        or pending_character_id != character.get("id")
        or (character.get("map_id"), character.get("instance_id", 0))
        != (MAP_ID, INSTANCE_ID)
        or in_combat
    ):
        raise ValueError("Rii portal callback is not pending for this character")
    installed_route = departure_route()
    if route is not None and route != installed_route:
        raise ValueError("Rii portal callback route differs from installed Zaap data")
    route = installed_route
    from wakfu_server.achievements import storage

    with store.connection() as db:
        db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account_id,))
        store.lock_character(db, account_id, generation, character["id"], selected=True)
        current = store.character(account_id, character["id"], db)
        if (current.get("map_id"), current.get("instance_id", 0)) != (
            MAP_ID,
            INSTANCE_ID,
        ):
            raise ValueError("Rii portal scene left its authorized map")
        starter = db.execute(
            "SELECT payload FROM character_achievement_events "
            "WHERE character_id=%s AND event_key=%s",
            (current["id"], START_EVENT_KEY),
        ).fetchone()
        if starter is None or starter["payload"] != _start_payload(current["id"]):
            raise ValueError("Rii portal scene has no authenticated start receipt")
        previous = db.execute(
            "SELECT payload FROM character_achievement_events "
            "WHERE character_id=%s AND event_key=%s",
            (current["id"], CALLBACK_EVENT_KEY),
        ).fetchone()
        payload = {
            "kind": "rii_zaap_scene_callback",
            "character_id": current["id"],
            "scenario_event": EVENT_ID,
        }
        if previous is None and not storage.record_event(
            db, current["id"], CALLBACK_EVENT_KEY, payload
        ):
            raise ValueError("Rii portal callback receipt raced")
        if previous is not None and previous["payload"] != payload:
            raise ValueError("Rii portal callback receipt differs")
        from wakfu_server import astrub_arrival_scene

        saved = store.transition_map_in_transaction(
            db, account_id, generation, current["id"], current, route["destination"]
        )
        packets = astrub_arrival_scene.enter(db, store, current, saved)
        saved = store.character(account_id, current["id"], db)
    return saved, tuple(packets), route
