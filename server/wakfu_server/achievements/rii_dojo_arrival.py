"""Native Celestial Dojo arrival choreography and its hidden carrier mission.

Official capture 2026-11-12, frames 8390-8495 of the private session: entering
map 1388 makes the original server send scenario 2543 events 22403 (the dojo
scene actor identities) and 22490 (ready, one zero argument). The installed
client answers with its scenario callback, and the server then completes
objective 11542 and hidden carrier mission 5592. No player-visible journal row
exists for that carrier, so it never receives an activation announcement.

The dojo fight bootstrap in the same capture uses terrain effect template 378
and fight model 14 for all seven Airyna lessons. Those constants are exported
here so the combat placement policy keeps one reviewed authority.
"""

import struct
from copy import deepcopy

SCENARIO = 2543
ACTORS = 22403
READY = 22490
DOJO_MAP = 1388
CARRIER = 5592
CARRIER_OBJECTIVE = 11542
TERRAIN_EFFECT = 378
LESSON_FIGHT_MODEL = 14
RECEIPT = "rii-dojo-arrival-carrier:%d"


def scene_uids(db, map_id=DOJO_MAP):
    """Scene actor identities the dojo script must bind, excluding dialogue speakers.

    The official event lists seventeen identities in the same allocation block as
    Airyna but never her own: the script binds the training props, not the quest
    giver. Publishing a dialogue speaker there would point the client script at
    the wrong actor, so only non-speaker scene actors may be announced.
    """
    speakers = {
        row["actor_id"]
        for row in db.execute(
            "SELECT actor_id FROM world_dialogue_npcs "
            "WHERE map_id=%s AND instance_id=0 AND enabled",
            (map_id,),
        )
    }
    return sorted(
        row["actor_id"]
        for row in db.execute(
            "SELECT actor_id FROM world_native_npc_placements "
            "WHERE map_id=%s AND instance_id=0",
            (map_id,),
        )
        if row["actor_id"] not in speakers
    )


def presentation(event, arguments=()):
    from wakfu_server.dungeon_main_completion import presentation_packet

    return presentation_packet(
        {
            "scenario_id": SCENARIO,
            "event_id": event,
            "parameters": [int(value) for value in arguments],
        }
    )


def arrival_packets(uids):
    """The two packets the original server publishes on dojo arrival."""
    identities = [int(value) for value in uids]
    if any(
        type(value) is not int or not -(1 << 63) <= value < (1 << 63)
        for value in identities
    ):
        raise ValueError("Invalid dojo scene actor identity")
    return [presentation(ACTORS, identities), presentation(READY, (0,))]


def validate_carrier(definition):
    if (
        not isinstance(definition, dict)
        or definition.get("d") != CARRIER
        or definition.get("native_class") != "aJM"
        or definition.get("aqb") is not True
        or [row.get("d") for row in definition.get("cjJ", ())] != [CARRIER_OBJECTIVE]
        or any(
            row.get("ckc") or row.get("cke") or row.get("ckf")
            for row in definition.get("cjJ", ())
        )
        or definition.get("cjK") != []
        or definition.get("cjU", 0) != 0
        or definition.get("cjL", 0) != 0
        or definition.get("getDuration") != 0
    ):
        raise ValueError("Rii dojo carrier differs from the native definition")
    return definition


def carrier_definition(db):
    row = db.execute(
        "SELECT data FROM native_quest_metadata_definitions WHERE revision="
        "(SELECT revision FROM native_quest_metadata_releases "
        "ORDER BY imported_at DESC LIMIT 1) AND definition_id=%s",
        (CARRIER,),
    ).fetchone()
    if row is None:
        raise ValueError("Missing native Rii dojo carrier definition")
    return validate_carrier(row["data"]["native"])


def deliver_callback(store, account_id, generation, source):
    """Settle one authenticated dojo-ready callback inside its own transaction."""
    with store.connection() as db:
        store.lock_character(db, account_id, generation, source["id"], selected=True)
        character = store.character(account_id, source["id"], db)
        if any(
            character[key] != source[key]
            for key in ("map_id", "instance_id", "x", "y", "z")
        ):
            raise ValueError("Dojo arrival scene position changed")
        return settle(db, store, character, READY)


def settle(db, store, character, event, *, state=None):
    """Complete the dojo carrier once per character, from its real client callback.

    The caller owns the transaction, the account/session fences and delivery.
    A replayed callback returns no packets; only an authenticated dojo scene
    position can produce progress.
    """
    if event != READY or character.get("map_id") != DOJO_MAP:
        return []
    from . import storage, wire

    before = storage.load_locked(db, character["id"]) if state is None else state
    if (
        CARRIER_OBJECTIVE in before["objectives"]
        or CARRIER in before["completed"]
        or CARRIER in before["running"]
    ):
        return []
    definition = carrier_definition(db)
    now_ms = int(store.now().timestamp() * 1000)
    if not storage.record_event(
        db,
        character["id"],
        RECEIPT % CARRIER_OBJECTIVE,
        {
            "kind": "rii_dojo_arrival_carrier",
            "quest_id": CARRIER,
            "objective_id": CARRIER_OBJECTIVE,
            "scenario": SCENARIO,
            "event": READY,
        },
    ):
        raise ValueError("Rii dojo carrier receipt exists without progress")
    after = deepcopy(before)
    after["objectives"] = sorted(set(after["objectives"]) | {CARRIER_OBJECTIVE})
    after["completed"] = sorted(set(after["completed"]) | {CARRIER})
    after["completion_dates"][str(CARRIER)] = now_ms
    after["recent"] = (after["recent"] + [{"id": CARRIER, "date_ms": now_ms}])[-255:]
    storage.store(db, character["id"], after)
    return wire.changes(
        character["id"],
        before,
        after,
        [CARRIER_OBJECTIVE],
        [CARRIER],
        now_ms,
        definitions={CARRIER: definition},
    )
