"""Owner-scoped, reconnect-stable alternating hazards for reviewed stories.

This adapter neither changes health nor moves an actor itself. A real movement
producer supplies the owned landing token; the trusted executor applies a fall
through the existing position registry before its once-only receipt commits.
"""

from hashlib import sha256

from wakfu_server.achievements import storage

SCHEMA = "owned-story-trap-cycle-v1"


def _point(value):
    return (
        isinstance(value, (list, tuple))
        and len(value) == 3
        and all(type(component) is int for component in value)
    )


def policy(document):
    """Require explicit timing and source-backed positions, never a default."""
    if (
        type(document) is not dict
        or document.get("schema") != SCHEMA
        or not isinstance(document.get("id"), str)
        or not document["id"]
        or len(document["id"]) > 64
        or type(document.get("map_id")) is not int
        or document["map_id"] <= 0
        or not document.get("provenance")
        or type(document.get("phase_ms")) is not int
        or not 1000 <= document["phase_ms"] <= 60000
        or type(document.get("fall_animation_ms")) is not int
        or not 0 < document["fall_animation_ms"] <= document["phase_ms"]
        or not _point(document.get("reset_position"))
        or not isinstance(document.get("requires"), list)
        or not document["requires"]
        or any(not isinstance(step, str) or not step for step in document["requires"])
        or len(set(document["requires"])) != len(document["requires"])
        or any(
            type(document.get(key)) is not int or document[key] <= 0
            for key in ("scenario", "fall_event", "opening_event", "closing_event")
        )
    ):
        raise ValueError("Missing explicit reviewed trap cycle")
    tiles = document.get("tiles")
    if not isinstance(tiles, list) or not tiles:
        raise ValueError("Trap cycle has no native hazard tiles")
    identities, positions, states = set(), set(), set()
    for tile in tiles:
        if (
            type(tile) is not dict
            or set(tile) != {"object_id", "position", "initial_state"}
            or type(tile["object_id"]) is not int
            or tile["object_id"] <= 0
            or tile["object_id"] in identities
            or not _point(tile["position"])
            or tuple(tile["position"]) in positions
            or type(tile["initial_state"]) is not int
            or tile["initial_state"] not in (0, 1)
        ):
            raise ValueError("Invalid or repeated native trap tile")
        identities.add(tile["object_id"])
        positions.add(tuple(tile["position"]))
        states.add(tile["initial_state"])
    if states != {0, 1} or tuple(document["reset_position"]) in positions:
        raise ValueError("Trap cycle needs a safe reset and complementary paths")
    return document


def clock(document, epoch_ms, now_ms):
    """Project absolute phase without accumulating scheduler/reconnect drift."""
    selected = policy(document)
    if any(type(value) is not int or value < 0 for value in (epoch_ms, now_ms)):
        raise ValueError("Trap clock requires authoritative integer milliseconds")
    elapsed = max(0, now_ms - epoch_ms)
    phase = elapsed // selected["phase_ms"]
    return dict(
        phase=phase,
        next_transition_ms=epoch_ms + (phase + 1) * selected["phase_ms"],
        state_effects=[
            dict(
                kind="element_state",
                object_id=tile["object_id"],
                state=tile["initial_state"] ^ (phase % 2),
                visible=True,
                usable=False,
                blocks_movement=False,
            )
            for tile in selected["tiles"]
        ],
    )


def _qualified(db, store, character, configuration, *, lock=True, check_position=True):
    from wakfu_server import owned_story_controller

    selected, completed = owned_story_controller._scope(
        db, store, character, lock=lock, check_position=check_position
    )
    supplied = configuration.get("topology", {}).get("owned_story_controller")
    if owned_story_controller._digest(supplied) != owned_story_controller._digest(
        selected
    ):
        raise ValueError("Trap cycle differs from the owner's frozen story")
    document = selected.get("trap_cycle")
    if document is None:
        return None, selected, completed
    document = policy(document)
    if document["map_id"] != selected["map_id"] or not set(document["requires"]) <= {
        step["id"] for step in selected["steps"]
    }:
        raise ValueError("Trap cycle belongs to a different native map")
    return document, selected, completed


def projection(db, store, character, configuration, now_ms=None, *, initialize=True):
    """Project hazards only after an actual earned puzzle-start receipt.

    Initializing callers own the account barrier and transaction. Read-only
    movement/scene projections pass initialize=False: they acquire no owner
    locks, compare map/instance ownership rather than a racing movement XYZ,
    never create a clock, and leave a missing clock inactive. The separate
    prefix cannot be confused with the controller's once-only story steps.
    """
    from wakfu_server import owned_story_controller

    if type(initialize) is not bool:
        raise ValueError("Invalid trap clock initialization policy")
    document, story, completed = _qualified(
        db, store, character, configuration, lock=initialize, check_position=initialize
    )
    if document is None or not set(document["requires"]) <= completed:
        return dict(active=False, state_effects=[], reset=None)
    if now_ms is None:
        now_ms = int(store.now().timestamp() * 1000)
    if type(now_ms) is not int or now_ms < 0:
        raise ValueError("Invalid authoritative trap time")
    key = f'owned-story-traps:{document["id"]}:{character["instance_id"]}:epoch'
    receipt = db.execute(
        "SELECT payload FROM character_achievement_events WHERE character_id=%s AND event_key=%s",
        (character["id"], key),
    ).fetchone()
    expected = dict(
        schema=SCHEMA,
        owner=character["id"],
        instance_id=character["instance_id"],
        profile_sha256=owned_story_controller._digest(story),
    )
    if receipt is None:
        if not initialize:
            return dict(active=False, state_effects=[], reset=None)
        payload = dict(expected, epoch_ms=now_ms)
        if not storage.record_event(db, character["id"], key, payload):
            raise ValueError("Trap clock initialization raced")
    else:
        payload = receipt["payload"]
        if any(payload.get(key) != value for key, value in expected.items()):
            raise ValueError("Trap clock belongs to another owner or profile")
    result = clock(document, payload["epoch_ms"], now_ms)
    active_ids = {
        effect["object_id"]
        for effect in result["state_effects"]
        if effect["state"] == 1
    }
    position = tuple(character[key] for key in ("x", "y", "z"))
    hit = next(
        (
            tile["object_id"]
            for tile in document["tiles"]
            if tuple(tile["position"]) == position and tile["object_id"] in active_ids
        ),
        None,
    )
    result.update(
        active=True,
        hazard_object=hit,
        reset=(
            None
            if hit is None
            else dict(
                position=list(document["reset_position"]),
                scenario=document["scenario"],
                native_event=document["fall_event"],
                delay_ms=document["fall_animation_ms"],
                due_ms=now_ms + document["fall_animation_ms"],
            )
        ),
    )
    return result


def on_landing(
    db, store, character, configuration, *, movement_token, apply_effects, now_ms=None
):
    """Apply one real landing atomically; replay never moves or animates twice."""
    if not isinstance(movement_token, str) or not 1 <= len(movement_token) <= 256:
        raise ValueError("Trap landing requires its authenticated movement token")
    state = projection(db, store, character, configuration, now_ms)
    return _apply_landing(db, store, character, state, movement_token, apply_effects)


def on_tick(db, store, character, configuration, *, apply_effects, now_ms=None):
    """A phase can raise a spike under a stationary player as well as a walker.

    Each absolute phase is its own server-owned receipt. Repeated scheduler
    ticks cannot animate or reset the same owner twice during that phase.
    """
    state = projection(db, store, character, configuration, now_ms)
    return _apply_landing(
        db,
        store,
        character,
        state,
        "trap-timer-phase:" + str(state.get("phase", -1)),
        apply_effects,
    )


def _apply_landing(db, store, character, state, movement_token, apply_effects):
    if not state["active"] or state["reset"] is None:
        return dict(applied=False, packets=[], projection=state)
    token = sha256(movement_token.encode()).hexdigest()
    key = f'owned-story-trap-fall:{character["instance_id"]}:{token}'
    old = db.execute(
        "SELECT payload FROM character_achievement_events WHERE character_id=%s AND event_key=%s",
        (character["id"], key),
    ).fetchone()
    if old is not None:
        return dict(applied=False, packets=[], projection=state)
    if not callable(apply_effects):
        raise ValueError("Trap landing has no native position executor")
    packets = list(apply_effects(db, store, character, state))
    receipt = dict(
        schema=SCHEMA,
        owner=character["id"],
        instance_id=character["instance_id"],
        hazard_object=state["hazard_object"],
        movement_sha256=token,
        reset=state["reset"],
    )
    if not storage.record_event(db, character["id"], key, receipt):
        raise ValueError("Trap fall raced its native position commit")
    return dict(applied=True, packets=packets, projection=state)
