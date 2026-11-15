"""Transactional mission chain for the native Incarnam tutorial.

Producers must authenticate and qualify their gameplay event before calling
``settle``. The event names are internal server facts, never client input.
"""

from copy import deepcopy
import struct

from . import mission_dependencies, mission_progress, storage, wire

MAP_ID = 1361
ONE_TIME_PRESENTATIONS = frozenset((22354, 22524))
STAGES = (
    (5135, 10564, "first_wodent_victory"),
    (5136, 10565, "wood_harvest"),
    (5137, 10566, "key_crafted"),
    (5138, 10567, "portal_opened"),
    (5139, 10568, "rii_intro_finished"),
)


def claim_presentation(db, character_id, event_id):
    """Reserve a one-shot presentation in the producer's transaction."""
    if (
        type(character_id) is not int
        or character_id <= 0
        or event_id not in ONE_TIME_PRESENTATIONS
    ):
        raise ValueError("Invalid one-time Incarnam presentation")
    return storage.record_event(
        db,
        character_id,
        f"incarnam-presentation:{event_id}",
        {"kind": "incarnam_presentation", "event_id": event_id},
    )


def scenario_packet(event, *arguments):
    """Encode one native Incarnam presentation event with integer arguments."""
    if event not in (
        21800,
        22500,
        22505,
        22519,
        22521,
        22522,
        22525,
        22566,
        22351,
        22353,
        22354,
        22356,
        22357,
        22358,
        22359,
    ):
        raise ValueError("Unknown Incarnam scenario presentation")
    if len(arguments) > 255 or any(type(value) is not int for value in arguments):
        raise ValueError("Invalid Incarnam scenario arguments")
    return (
        13411,
        struct.pack(">BiiB", 0, event, 2500, len(arguments))
        + b"".join(struct.pack(">q", value) for value in arguments),
    )


def interface_recovery_packet():
    """Restore native interface shortcuts after leaving the tutorial scene.

    Installed Lua2500's end event22500 calls prepareUI before restoring its
    shortcuts. Its obsolete extraInterfaceBarDrawerButton lookup throws, so
    inventory and quest shortcuts remain disabled. Native2071/16608 restores
    the individual interface shortcuts before touching widgets, without
    changing quest visibility, starting a cinematic or publishing actors.
    Call only after Incarnam exit or on a completed/skipped Rii login; active
    tutorial scenes intentionally restrict these shortcuts.
    """
    return 13411, struct.pack(">BiiB", 0, 16608, 2071, 0)


def initial_packets(state, *, planting_guide_seen=False):
    """Restore the scene's visual state without replaying completed events."""
    step = next(
        (
            step
            for identity, step in (
                (5139, 50),
                (5138, 40),
                (5137, 30),
                (5136, 20),
                (5135, 10),
            )
            if identity in state["running"]
        ),
        None,
    )
    if step is None:
        return []
    if step == 20 and planting_guide_seen:
        step = 25
    packets = [scenario_packet(21800), scenario_packet(22505, step)]
    if step == 25:
        packets.append(scenario_packet(22566))
    return packets


def is_resumed_scene_ready(character, state, callback, pending):
    """Accept the native load callback after an existing scene is restored.

    Lua 2500 always answers 21800 when loaded. Only the fresh cinematic
    transition arms the arrival chain; reconnect restores the saved step.
    """
    from wakfu_server.intro_cinematic import private_instance_id

    return (
        callback == 21800
        and pending is None
        and character.get("map_id") == MAP_ID
        and type(character.get("id")) is int
        and character["id"] > 0
        and character.get("instance_id") == private_instance_id(character["id"])
        and any(identity in state.get("running", ()) for identity, _, _ in STAGES)
    )


def cinematic_camera_travel(character_id, callback):
    """Client-only camera relocation around the native Incarnam arrival scene.

    The server position remains at the owned spawn. The client hides and locks
    its character during this sequence and is restored before gameplay resumes.
    """
    if type(character_id) is not int or character_id <= 0:
        raise ValueError("Invalid Incarnam scene owner")
    if callback == 22519:
        x, y, z = 434, 362, 1
    elif callback == 22521:
        x, y, z = 0, 0, 0
    else:
        raise ValueError("Invalid Incarnam camera transition")
    return [
        (13259, struct.pack(">qiihBB", character_id, x, y, z, 0, 0)),
        (12318, struct.pack(">ii", x, y)),
    ]


# These native trigger cells and IDs were recorded on the official tutorial
# path. Only validated movement may be submitted here.
_WALK_TRIGGERS = {(5, 0, -4): 34569, (12, 0, -16): 34570, (12, -9, -16): 34571}


def walking_guide_packets(character, state, path):
    from wakfu_server.intro_cinematic import private_instance_id

    if (
        character.get("map_id") != MAP_ID
        or type(character.get("id")) is not int
        or character.get("instance_id") != private_instance_id(character["id"])
        or 5135 not in state["running"]
    ):
        return []
    result = []
    for before, after in zip(path, path[1:]):
        point = (after["x"], after["y"], after["z"])
        trigger = _WALK_TRIGGERS.get(point)
        if trigger is None:
            continue
        forward = (
            after["x"] > before["x"]
            if trigger in (34569, 34570)
            else after["y"] < before["y"]
        )
        result.append(scenario_packet(22351 if forward else 22353, trigger))
    return result


def resume_walk_guide(character, state):
    """Restore a useful next arrow from the saved position on reconnect."""
    from wakfu_server.intro_cinematic import private_instance_id

    if (
        character.get("map_id") != MAP_ID
        or type(character.get("id")) is not int
        or character.get("instance_id") != private_instance_id(character["id"])
        or 5135 not in state["running"]
    ):
        return None
    if character["x"] >= 10 and character["y"] <= -9:
        trigger = 34571
    elif character["x"] >= 10:
        trigger = 34570
    else:
        trigger = 34569
    return scenario_packet(22351, trigger)


def planting_guide_seen(db, character_id):
    return (
        db.execute(
            "SELECT 1 FROM character_achievement_events WHERE character_id=%s AND event_key=%s",
            (character_id, "incarnam-planting-guide:finished"),
        ).fetchone()
        is not None
    )


def finish_planting_guide(store, account_id, generation, character_id):
    """Persist completion of the owner connection's cinematic callback."""
    from wakfu_server.intro_cinematic import private_instance_id

    with store.connection() as db:
        store.lock_character(db, account_id, generation, character_id, selected=True)
        character = store.character(account_id, character_id, db)
        state = storage.load_locked(db, character_id)
        if (
            character.get("map_id") != MAP_ID
            or character.get("instance_id") != private_instance_id(character_id)
            or 5136 not in state["running"]
        ):
            raise ValueError("Incarnam planting guide no longer active")
        return storage.record_event(
            db,
            character_id,
            "incarnam-planting-guide:finished",
            {"kind": "incarnam_planting_guide_finished"},
        )


def blocked_path(store, account_id, generation, location, body):
    """Qualify the recorded position trigger that starts the planting guide."""
    from wakfu_server.intro_cinematic import private_instance_id

    if body != struct.pack(">qHH", 34658, 5, 0):
        return False
    with store.connection() as db:
        store.lock_character(db, account_id, generation, location["id"], selected=True)
        character = store.character(account_id, location["id"], db)
        if (
            character.get("map_id") != MAP_ID
            or character.get("instance_id") != private_instance_id(character["id"])
            or abs(character["x"] - 12) + abs(character["y"] + 32) > 6
            or abs(character["z"] + 13) > 4
        ):
            raise ValueError("Incarnam tutorial trigger is out of range")
        state = storage.load_locked(db, character["id"])
        return 5136 in state["running"] and not planting_guide_seen(db, character["id"])


def _definition(db, identity, objective):
    row = db.execute(
        "SELECT data FROM native_quest_metadata_definitions WHERE revision="
        "(SELECT revision FROM native_quest_metadata_releases ORDER BY imported_at DESC LIMIT 1) "
        "AND definition_id=%s",
        (identity,),
    ).fetchone()
    if not row:
        raise ValueError("Missing Incarnam tutorial mission definition")
    native = row["data"]["native"]
    if (
        native.get("d") != identity
        or native.get("native_class") != "aJM"
        or native.get("aqb") is not False
        or native.get("cjI") != ""
        or native.get("cjU") != 0
        or native.get("getDuration") != 0
        or [item.get("d") for item in native.get("cjJ", ())] != [objective]
    ):
        raise ValueError("Unexpected Incarnam tutorial mission definition")
    return native


def enter(db, store, character, *, previous_map):
    """Start tutorial on authorized cinematic-to-Incarnam travel only."""
    if previous_map != 1465 or character.get("map_id") != MAP_ID:
        return []
    before = storage.load_locked(db, character["id"])
    identity, objective, _ = STAGES[0]
    if identity in before["running"] or identity in before["completed"]:
        return []
    _definition(db, identity, objective)
    now_ms = int(store.now().timestamp() * 1000)
    if not storage.record_event(
        db,
        character["id"],
        "incarnam-start:5135",
        {"kind": "incarnam_start", "accepted_at_ms": now_ms},
    ):
        raise ValueError("Incarnam start receipt exists without mission state")
    after = deepcopy(before)
    after["running"] = sorted(set(after["running"]) | {identity})
    mission_progress.auto_track(after, identity)
    storage.store(db, character["id"], after)
    return wire.changes(character["id"], before, after, [], [], now_ms)


def settle(db, store, character, *, event, token):
    """Settle an already-authorized gameplay fact and activate the next quest.

    The final mission ends on Rii's scene callback, through the separate Rii
    callback handler, not on the second combat or arrival alone.
    """
    if character.get("map_id") != MAP_ID:
        return []
    if not isinstance(token, str) or not token:
        raise ValueError("Invalid Incarnam gameplay receipt")
    index = next((i for i, stage in enumerate(STAGES[:-1]) if stage[2] == event), None)
    if index is None:
        raise ValueError("Unknown Incarnam gameplay event")
    identity, objective, _ = STAGES[index]
    before = storage.load_locked(db, character["id"])
    if identity not in before["running"] or objective in before["objectives"]:
        return []
    native = _definition(db, identity, objective)
    next_identity, next_objective, _ = STAGES[index + 1]
    _definition(db, next_identity, next_objective)
    now_ms = int(store.now().timestamp() * 1000)
    after, intents, objectives, completed = mission_progress.advance_objective(
        before,
        native,
        objective,
        character=character,
        store=store,
        now_ms=now_ms,
    )
    if completed != [identity] or objectives != [objective]:
        raise ValueError("Unexpected Incarnam objective transition")
    if (
        next_identity not in after["running"]
        and next_identity not in after["completed"]
    ):
        if not storage.record_event(
            db,
            character["id"],
            f"incarnam-start:{next_identity}",
            {"kind": "incarnam_start", "accepted_at_ms": now_ms},
        ):
            raise ValueError("Incarnam start receipt exists without mission state")
        after["running"] = sorted(set(after["running"]) | {next_identity})
        mission_progress.auto_track(after, next_identity)
    if not storage.record_event(
        db,
        character["id"],
        f"incarnam:{identity}:{token}",
        {"kind": event, "objective_id": objective, "accepted_at_ms": now_ms},
    ):
        raise ValueError("Incarnam receipt exists without mission progress")
    packets = mission_dependencies.settle(
        db,
        store,
        character,
        before,
        (after, intents, objectives, completed),
        {},
        (),
        now_ms=now_ms,
    )["packets"]
    if index == 0:
        from . import incarnam_resources

        packets.extend(incarnam_resources.first_barrier_packets(character, after))
        packets.extend(incarnam_resources.give_seed(db, store, character))
        # The first-fight cinematic is published after the combat return,
        # when the player's world actor is available again.
        return packets
    return [*packets, scenario_packet((22356, 22357, 22358)[index - 1])]
