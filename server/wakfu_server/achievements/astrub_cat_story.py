"""Owned quest5568 choreography around the existing three-room cat dungeon.

The installed scenario1340 supplies presentation and native ally4691 supplies
combat behavior. Room formations remain the reviewed local dungeon plan; their
original official server construction was not present in the preserved sniff.
Only committed owned room victories can start the corresponding story scenes.
"""

from copy import deepcopy
import struct

from . import (
    storage,
    mission_progress,
    mission_dependencies,
    tutorial_presentation_once,
)
from .astrub_cat_story_authority import context, combat_helper_admission
from wakfu_server import astrub_cat_presentation as presentation

SCHEMA = "wakemu.astrub-cat-story.v1"
QUEST_ID = 5568
MAP_ID = 312
ROOM_OBJECTIVES = {1: 11511, 2: 11512, 3: 11513}
CALLBACK_EVENTS = frozenset((23920, 23922, 23924, 23926, 23927, 23928))


def _key(instance, suffix):
    return f"astrub-cat-story:{instance}:{suffix}"


def _event(db, owner, key):
    row = db.execute(
        "SELECT payload FROM character_achievement_events WHERE character_id=%s AND event_key=%s",
        (owner, key),
    ).fetchone()
    return None if row is None else row["payload"]


def _done(db, owner, instance, event):
    return _event(db, owner, _key(instance, f"callback:{event}")) is not None


def _definition(db):
    row = db.execute(
        "SELECT data FROM native_quest_metadata_definitions WHERE revision="
        "(SELECT revision FROM native_quest_metadata_releases ORDER BY imported_at DESC LIMIT 1) "
        "AND definition_id=%s",
        (QUEST_ID,),
    ).fetchone()
    if row is None or row["data"]["native"].get("d") != QUEST_ID:
        raise ValueError("Missing native cat-house mission definition")
    return row["data"]["native"]


def _advance(db, store, character, objective):
    before = storage.load_locked(db, character["id"])
    definition = _definition(db)
    now_ms = int(store.now().timestamp() * 1000)
    planned = mission_progress.advance_objective(
        before,
        definition,
        objective,
        character=character,
        store=store,
        now_ms=now_ms,
    )
    result = mission_dependencies.settle(
        db,
        store,
        character,
        before,
        planned,
        {QUEST_ID: definition},
        (),
        now_ms=now_ms,
    )
    return list(result["packets"])


def _members(db, instance, room):
    row = db.execute(
        "SELECT g.members FROM dungeon_room_spawn_receipts r JOIN combat_groups g "
        "ON g.map_id=r.asset_map_id AND g.instance_id=r.instance_id AND g.group_id=r.group_id "
        "WHERE r.instance_id=%s AND r.room_order=%s",
        (instance, room),
    ).fetchone()
    if row is None or not isinstance(row["members"], list) or len(row["members"]) != 3:
        raise ValueError("Cat-house scene lacks its owned room actors")
    return row["members"]


def _victory(db, character, instance, room):
    row = db.execute(
        "SELECT e.fight_id,e.result FROM dungeon_room_encounters e "
        "JOIN combat_fight_participants p ON p.fight_id=e.fight_id "
        "JOIN combat_fights f ON f.id=e.fight_id "
        "WHERE e.instance_id=%s AND e.room_order=%s AND e.encounter_scope='main' "
        "AND e.status='victory' AND p.character_id=%s AND p.account_id=%s "
        "AND p.team=e.player_team AND f.status='finished' ORDER BY e.fight_id DESC LIMIT 1",
        (instance, room, character["id"], character["account_id"]),
    ).fetchone()
    if row is None or row["result"].get("victory") is not True:
        return None
    return row


def _initialize(db, character, scope):
    if scope["receipt"] is not None:
        receipt = scope["receipt"]
        if (
            not isinstance(receipt, dict)
            or receipt.get("schema") != SCHEMA
            or receipt.get("owner") != character["id"]
            or receipt.get("instance_id") != scope["instance"]
        ):
            raise ValueError("Cat-house story receipt has another owner")
        presentation._identities(receipt.get("cat_ids", ()), 12)
        presentation._identities(receipt.get("nekark_ids", ()), 5)
        if set(receipt["cat_ids"]) & set(receipt["nekark_ids"]):
            raise ValueError("Cat-house story actor identities overlap")
        first = _members(db, scope["instance"], 1)
        if set(receipt["cat_ids"][:3]) != {member["id"] for member in first}:
            raise ValueError("Cat-house story actor receipt changed its real room")
        return receipt
    if scope["room"] != 1 or scope["progress"]["status"] != "active":
        return None
    from wakfu_server.npc_actor_identity import allocate_block

    first = _members(db, scope["instance"], 1)
    if sorted(member["ref"] for member in first) != [2616, 2616, 2616]:
        raise ValueError("Cat-house initial room differs from the reviewed roster")
    base = allocate_block(db, 32)
    payload = dict(
        schema=SCHEMA,
        owner=character["id"],
        instance_id=scope["instance"],
        cat_ids=[member["id"] for member in first] + [-(base + i) for i in range(9)],
        nekark_ids=[-(base + 16 + i) for i in range(5)],
        authority="installed1340-presentation-and-reviewed-three-room-rosters",
    )
    if not storage.record_event(
        db, character["id"], _key(scope["instance"], "start"), payload
    ):
        raise ValueError("Cat-house story start raced")
    return payload


def _bootstrap_packets(db, character, instance, receipt):
    ids = receipt["cat_ids"]
    packets = list(presentation.visual_packets(presentation.CAT_LAYOUT[3:], ids[3:]))
    packets.append(presentation.bootstrap(ids))
    if _done(db, character["id"], instance, 23920):
        packets.append(presentation.remove_visuals(ids[3:]))
    return packets


def _pending_scene(db, character, instance):
    if not _done(db, character["id"], instance, 23920):
        return 23920, None
    for room, event in presentation.ROOM_VICTORY_SCENES.items():
        victory = _victory(db, character, instance, room)
        if victory is None:
            return None, None
        if not _done(db, character["id"], instance, event):
            return event, victory
    if not _done(db, character["id"], instance, 23927):
        return 23927, None
    if not _done(db, character["id"], instance, 23928):
        return 23928, None
    return None, None


def _move(db, character, position):
    result = db.execute(
        "UPDATE characters SET x=%s,y=%s,z=%s "
        "WHERE id=%s AND account_id=%s AND map_id=%s AND instance_id=%s",
        (
            *position,
            character["id"],
            character["account_id"],
            MAP_ID,
            character["instance_id"],
        ),
    )
    if result.rowcount != 1:
        raise ValueError("Cat-house presentation lost its owned position")
    character.update(zip(("x", "y", "z"), position))


def _scene(db, store, character, scope, receipt, event, victory=None):
    instance = scope["instance"]
    key = _key(instance, f"scene:{event}")
    expected = dict(
        kind="owned_cat_story_scene",
        owner=character["id"],
        instance_id=instance,
        event_id=event,
    )
    if victory is not None:
        expected["fight_id"] = victory["fight_id"]
    existing = _event(db, character["id"], key)
    show = True
    if event != 23927:
        show = tutorial_presentation_once.claim(
            db,
            character["id"],
            presentation.SCENARIO_ID,
            event,
            legacy=(
                {
                    "prefix": "astrub-cat-story:",
                    "payload": dict(
                        kind="owned_cat_story_scene",
                        owner=character["id"],
                        event_id=event,
                    ),
                },
            ),
        )
    packets = []
    if existing is None:
        if event in presentation.ROOM_VICTORY_SCENES.values():
            room = next(
                room
                for room, candidate in presentation.ROOM_VICTORY_SCENES.items()
                if candidate == event
            )
            if victory is None:
                raise ValueError("Cat-house room scene requires its real winning fight")
            packets += _advance(db, store, character, ROOM_OBJECTIVES[room])
        if event == 23928:
            if not _done(db, character["id"], instance, 23927):
                raise ValueError("Nekark scene requires the completed cat-house exit")
        if not storage.record_event(db, character["id"], key, expected):
            raise ValueError("Cat-house scene receipt raced")
    elif existing != expected:
        raise ValueError("Cat-house scene receipt changed")
    if event in (23922, 23926):
        from . import earned_achievement_links

        packets.extend(
            earned_achievement_links.settle(
                db,
                store,
                character,
                source_quest=QUEST_ID,
                source_objective=ROOM_OBJECTIVES[1 if event == 23922 else 3],
                event_key=key,
            )
        )
    if not show:
        # An old scene may be suppressed in a new instance or after reconnect.
        # Its actual victory/objective settlement above still occurs. Complete
        # only the owned mechanical callback; no client callback will arrive.
        if event == 23928:
            _move(db, character, presentation.PLAYER_POSITIONS[event])
        if not _done(db, character["id"], instance, event):
            extra, _ = _acknowledge(db, store, character, scope, event)
            packets.extend(extra)
        return packets
    if event == 23927:
        packets.append(presentation.packet(event))
    else:
        args = ()
        if event == 23924:
            boss_members = _members(db, instance, 3)
            by_ref = {member["ref"]: member["id"] for member in boss_members}
            if set(by_ref) != {1816, 2616, 2617}:
                raise ValueError("Cat-house boss scene lost its real room roster")
            args = (by_ref[2616], by_ref[2617], by_ref[1816])
        scene = (
            presentation.nekark_scene(character["id"], receipt["nekark_ids"])
            if event == 23928
            else presentation.scene(event, character["id"], *args)
        )
        _move(db, character, scene["position"])
        packets += list(scene["packets"])
    return packets


def poll(
    store, account_id, generation, character, *, pending_event=None, bootstrap=False
):
    """Offer each presentation once per character, retaining owned mechanics."""
    if character.get("map_id") != MAP_ID or character.get("instance_id", 0) <= 0:
        return None
    with store.connection() as db:
        store.lock_character(db, account_id, generation, character["id"], selected=True)
        current = store.character(account_id, character["id"], db)
        scope = context(db, current, allow_finished=True)
        if scope is None:
            return None
        receipt = _initialize(db, current, scope)
        if receipt is None:
            return None
        scope["receipt"] = receipt
        instance = scope["instance"]
        packets = (
            _bootstrap_packets(db, current, instance, receipt) if bootstrap else []
        )
        event, victory = _pending_scene(db, current, instance)
        marker = None if event is None else (instance, event)
        if event is not None and pending_event != marker:
            packets += _scene(db, store, current, scope, receipt, event, victory)
            if _done(db, current["id"], instance, event):
                marker = None
                next_event, _ = _pending_scene(db, current, instance)
                if (
                    next_event is not None
                    and _event(db, current["id"], _key(instance, f"scene:{next_event}"))
                    is not None
                ):
                    marker = (instance, next_event)
        finished = _done(db, current["id"], instance, 23928)
        current = store.character(account_id, current["id"], db)
    return dict(
        character=current,
        packets=tuple(packets),
        pending_event=marker,
        blocks_travel=marker is not None,
        finished=finished,
    )


def _acknowledge(db, store, current, scope, event):
    """Commit the real callback mechanics, including when presentation is seen."""
    instance = scope["instance"]
    show_guide = event == 23920 and tutorial_presentation_once.claim_guide(
        db,
        current["id"],
        170,
        legacy=(
            {
                "prefix": "astrub-cat-story:",
                "payload": dict(
                    kind="owned_cat_story_callback",
                    owner=current["id"],
                    event_id=23920,
                ),
            },
        ),
    )
    if not storage.record_event(
        db,
        current["id"],
        _key(instance, f"callback:{event}"),
        dict(
            kind="owned_cat_story_callback",
            owner=current["id"],
            instance_id=instance,
            event_id=event,
        ),
    ):
        raise ValueError("Cat-house callback already completed")
    packets, marker = [], None
    if event == 23920:
        packets.append(presentation.remove_visuals(scope["receipt"]["cat_ids"][3:]))
        if show_guide:
            packets.append(presentation.packet(23921))
    elif event == 23927:
        packets += _advance(db, store, current, 11514)
        packets += _scene(db, store, current, scope, scope["receipt"], 23928)
        if not _done(db, current["id"], instance, 23928):
            marker = (instance, 23928)
    elif event == 23928:
        packets += _advance(db, store, current, 11515)
        packets.append(presentation.remove_visuals(scope["receipt"]["nekark_ids"]))
        packets.append(presentation.packet(23929))
    elif event == 23926:
        packets += _scene(db, store, current, scope, scope["receipt"], 23927)
        marker = (instance, 23927)
    else:
        packets.append(presentation.packet(presentation.AFTER_SCENE_EVENTS[event]))
    return packets, marker


def callback(
    store, account_id, generation, character, body, *, pending_event, in_combat=False
):
    """Acknowledge only a previously offered owner/instance/stage callback."""
    if not isinstance(body, bytes) or len(body) != 4:
        raise ValueError("Invalid cat-house story callback")
    event = struct.unpack(">i", body)[0]
    if event not in CALLBACK_EVENTS:
        raise ValueError("Cat-house callback phase is not pending")
    with store.connection() as db:
        store.lock_character(db, account_id, generation, character["id"], selected=True)
        current = store.character(account_id, character["id"], db)
        scope = context(db, current, allow_finished=True)
        if scope is None or scope["receipt"] is None:
            raise ValueError("Cat-house callback lacks its owned story")
        instance = scope["instance"]
        if (
            _done(db, current["id"], instance, event)
            and _event(db, current["id"], _key(instance, f"scene:{event}")) is not None
        ):
            # A native callback may arrive after an already-seen scene was
            # settled mechanically. It cannot award or replay anything.
            return dict(
                character=current,
                packets=(),
                pending_event=pending_event,
                blocks_travel=pending_event is not None,
                finished=_done(db, current["id"], instance, 23928),
            )
        if in_combat or pending_event != (instance, event):
            raise ValueError("Cat-house callback phase is not pending")
        expected_event, _ = _pending_scene(db, current, instance)
        if expected_event != event:
            raise ValueError("Cat-house callback is out of order")
        if _event(db, current["id"], _key(instance, f"scene:{event}")) is None:
            raise ValueError("Cat-house callback scene was never offered")
        packets, marker = _acknowledge(db, store, current, scope, event)
        current = store.character(account_id, current["id"], db)
        finished = _done(db, current["id"], instance, 23928)
    return dict(
        character=current,
        packets=tuple(packets),
        pending_event=marker,
        blocks_travel=marker is not None,
        finished=finished,
    )


def defer_auto_exit(db, instance_id):
    """Keep a completed owned story instance until its native ending is acknowledged."""
    rows = db.execute(
        "SELECT c.id,p.state,e.payload FROM dungeon_instance_members m "
        "JOIN characters c ON c.id=m.character_id "
        "JOIN character_achievement_progress p ON p.character_id=c.id "
        "JOIN character_achievement_events e ON e.character_id=c.id AND e.event_key=%s "
        "WHERE m.instance_id=%s AND m.status='active' AND c.map_id=%s AND c.instance_id=%s",
        (_key(instance_id, "start"), instance_id, MAP_ID, instance_id),
    ).fetchall()
    for row in rows:
        payload = row["payload"]
        if (
            payload.get("schema") == SCHEMA
            and payload.get("owner") == row["id"]
            and payload.get("instance_id") == instance_id
            and QUEST_ID in row["state"]["running"]
            and 11515 not in row["state"]["objectives"]
        ):
            return True
    return False
