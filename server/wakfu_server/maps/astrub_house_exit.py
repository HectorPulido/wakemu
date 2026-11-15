"""Owned arrival-house exit through the captured native position trigger.

The installed exit cinematic uses an older Astrub coordinate system. Keep the
captured gameplay edge and objective without running that incompatible scene.
"""

import struct

MAP_ID = 895
ELEMENT_ID = 35386
ACTION_ID = 5
QUEST_ID = 5568
OBJECTIVE_ID = 11509
TRIGGER_CELL = (0, 1, 0)
# Official frame7210 ends the approach at(-1,1,0), then7211 sends WALKON.
CAPTURED_POSITIONS = frozenset((TRIGGER_CELL, (-1, 1, 0)))
DESTINATION = dict(map_id=527, instance_id=0, x=7, y=156, z=0)
EVENT_KEY = "astrub-house-exit:11509"


def handles_activation(character, body):
    return (
        isinstance(character, dict)
        and (character.get("map_id"), character.get("instance_id", 0)) == (MAP_ID, 0)
        and isinstance(body, bytes)
        and len(body) >= 8
        and struct.unpack_from(">q", body)[0] == ELEMENT_ID
    )


def _authorized_position(character, approved_positions=()):
    if (character.get("map_id"), character.get("instance_id", 0)) != (MAP_ID, 0):
        raise ValueError("Astrub house exit belongs to another scene")
    position = tuple(character.get(key) for key in ("x", "y", "z"))
    if position in CAPTURED_POSITIONS:
        return
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
        raise ValueError("Astrub house exit is outside its native trigger")
    approved = frozenset(approved_positions)
    if position not in approved or TRIGGER_CELL not in approved:
        raise ValueError("Astrub house exit is outside its native trigger")


def _route():
    from wakfu_server.combat_terrain import map_geometry

    position = [DESTINATION[key] for key in ("x", "y", "z")]
    if position not in map_geometry(DESTINATION["map_id"])["cells"]:
        raise ValueError(
            "Captured Astrub arrival position is not installed walkable ground"
        )
    return dict(
        source_map=MAP_ID,
        interactive_element_id=ELEMENT_ID,
        destination_id=0,
        direction=3,
        destination=dict(DESTINATION),
    )


def begin(store, account_id, generation, character, body, *, approved_positions=()):
    """Commit the exit objective and owned map transition in one transaction."""
    if (
        not isinstance(body, bytes)
        or len(body) != 12
        or struct.unpack(">qHH", body) != (ELEMENT_ID, ACTION_ID, 0)
    ):
        raise ValueError("Invalid native Astrub house exit activation")
    _authorized_position(character, approved_positions)
    route = _route()
    from wakfu_server.achievements import (
        storage,
        mission_progress,
        mission_dependencies,
    )

    with store.connection() as db:
        db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account_id,))
        store.lock_character(db, account_id, generation, character["id"], selected=True)
        current = store.character(account_id, character["id"], db)
        _authorized_position(current, approved_positions)
        if tuple(current[key] for key in ("x", "y", "z")) != tuple(
            character[key] for key in ("x", "y", "z")
        ):
            raise ValueError("Astrub house exit position changed during activation")
        before = storage.load_locked(db, current["id"])
        if (
            QUEST_ID not in before["running"]
            or 11508 not in before["objectives"]
            or OBJECTIVE_ID in before["objectives"]
        ):
            raise ValueError(
                "Complete the introduction before leaving the arrival house"
            )
        row = db.execute(
            "SELECT data FROM native_quest_metadata_definitions WHERE revision="
            "(SELECT revision FROM native_quest_metadata_releases ORDER BY imported_at DESC LIMIT 1) "
            "AND definition_id=%s",
            (QUEST_ID,),
        ).fetchone()
        if row is None or row["data"]["native"].get("d") != QUEST_ID:
            raise ValueError("Missing native Astrub arrival mission definition")
        definition = row["data"]["native"]
        now_ms = int(store.now().timestamp() * 1000)
        planned = mission_progress.advance_objective(
            before,
            definition,
            OBJECTIVE_ID,
            character=current,
            store=store,
            now_ms=now_ms,
        )
        if not storage.record_event(
            db,
            current["id"],
            EVENT_KEY,
            dict(
                kind="captured_astrub_house_exit",
                character_id=current["id"],
                quest_id=QUEST_ID,
                objective_id=OBJECTIVE_ID,
                element_id=ELEMENT_ID,
                source_map=MAP_ID,
                destination=route["destination"],
            ),
        ):
            raise ValueError(
                "Astrub house exit receipt already exists without progress"
            )
        outcome = mission_dependencies.settle(
            db,
            store,
            current,
            before,
            planned,
            {QUEST_ID: definition},
            (),
            now_ms=now_ms,
        )
        saved = store.transition_map_in_transaction(
            db,
            account_id,
            generation,
            current["id"],
            current,
            route["destination"],
        )
    return dict(character=saved, packets=tuple(outcome["packets"]), route=route)
