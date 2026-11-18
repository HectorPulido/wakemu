"""Native marker states earned by authenticated owned-story mechanics.

The existing world-state carrier and delta codec own hydration/presentation.
No inventory item, timed stat modifier, or synthetic HasState fact is created.
"""

from psycopg.types.json import Jsonb


def validate_descriptor(row, state_id):
    if (
        not isinstance(row, dict)
        or row.get("state_id") != state_id
        or type(row.get("maximum_level")) is not int
        or not 1 <= row["maximum_level"] <= 32767
        or row.get("duration_base") != -1
        or type(row.get("realtime_duration_base")) is not int
        or row["realtime_duration_base"] >= 0
        or row.get("skip_turn_timer") is not True
        or type(row.get("marker_effect_id")) is not int
        or row["marker_effect_id"] <= 0
        or row.get("marker_generic") != 400
        or row.get("marker_parameters") != [0, 0]
        or not isinstance(row.get("source_sha256"), str)
        or len(row["source_sha256"]) != 64
    ):
        raise ValueError("Owned story state lacks its pinned native marker program")
    return row


def descriptor(selected, state_id):
    from wakfu_server.owned_story_mechanics import sources

    return validate_descriptor(
        sources(selected).get("marker_states", {}).get(str(state_id)), state_id
    )


def has_state(character, reference):
    """Use real hydrated carriers; story markers retain their actual run scope."""
    for row in character.get("consumable_states", ()):
        if not isinstance(row, dict) or row.get("state_id") != reference:
            continue
        origin = row.get("native_origin")
        if origin is None:
            return True
        if not isinstance(origin, dict):
            continue
        if origin.get("kind") != "owned-story-native-marker":
            return True
        if origin.get("instance_id") == character.get("instance_id") and origin.get(
            "character_id"
        ) == character.get("id"):
            return True
    return False


def apply(db, store, character, selected, effect):
    from wakfu_server import consumable_buffs, consumable_buff_wire
    from wakfu_server import owned_story_controller as controller

    state_id = effect["state_id"]
    native = descriptor(selected, state_id)
    scoped, completed = controller._scope(db, store, character)
    if scoped != selected:
        raise ValueError("Native marker differs from its actual owned controller")
    steps = [step for step in selected["steps"] if effect in step["effects"]]
    if len(steps) != 1 or not set(steps[0]["requires"]) <= completed:
        raise ValueError("Native marker lacks its unique eligible mechanic producer")
    origin = dict(
        kind="owned-story-native-marker",
        character_id=character["id"],
        instance_id=character["instance_id"],
        state_id=state_id,
        profile_sha256=controller._digest(selected),
        source_sha256=native["source_sha256"],
        story_id=selected["id"],
        step_id=steps[0]["id"],
    )
    previous = store.character(character["account_id"], character["id"], db)
    existing = db.execute(
        "SELECT uid,native_origin FROM character_consumable_buffs "
        "WHERE character_id=%s AND state_id=%s FOR UPDATE",
        (character["id"], state_id),
    ).fetchone()
    if not effect["active"]:
        if existing is None or existing["native_origin"] is None:
            raise ValueError("Native marker consumption lacks its actual carrier")
        actual = existing["native_origin"]
        if any(
            actual.get(key) != origin[key]
            for key in (
                "kind",
                "character_id",
                "instance_id",
                "state_id",
                "profile_sha256",
                "source_sha256",
                "story_id",
            )
        ):
            raise ValueError("Native marker belongs to another owner or attempt")
        consumable_buffs.retire_states(
            store, db, character["id"], uids=(existing["uid"],)
        )
    else:
        if existing is not None:
            prior = existing["native_origin"]
            stale = None
            if (
                isinstance(prior, dict)
                and prior.get("kind") == "owned-story-native-marker"
                and prior.get("character_id") == character["id"]
                and prior.get("instance_id") != character["instance_id"]
            ):
                stale = db.execute(
                    "SELECT 1 FROM dungeon_instances i JOIN dungeon_instance_members m USING(instance_id) "
                    "WHERE i.instance_id=%s AND m.character_id=%s "
                    "AND i.status IN ('closed','completed') AND m.status='returned'",
                    (prior["instance_id"], character["id"]),
                ).fetchone()
            if stale is None:
                raise ValueError(
                    "Native marker already exists; its original carrier is preserved"
                )
            consumable_buffs.retire_states(
                store, db, character["id"], uids=(existing["uid"],)
            )
        carrier = dict(
            state_id=state_id,
            level=1,
            clock="event",
            duration_ms=0,
            maximum_level=native["maximum_level"],
            stacking="reject_duplicate",
            effect_ids=[],
            metadata=dict(
                native_realtime_duration_base=native["realtime_duration_base"],
                native_marker_effect_id=native["marker_effect_id"],
                native_marker_generic=400,
                source_sha256=native["source_sha256"],
            ),
        )
        db.execute(
            "INSERT INTO character_consumable_buffs(character_id,state_id,level,source_item_ref,"
            "source_item_uid,clock,duration_ms,remaining_ms,expires_ms,online_generation,online_anchor_ms,metadata,native_origin) "
            "VALUES(%s,%s,1,NULL,NULL,'event',0,0,NULL,NULL,NULL,%s,%s)",
            (character["id"], state_id, Jsonb(carrier), Jsonb(origin)),
        )
    current = store.character(character["account_id"], character["id"], db)
    packets = consumable_buff_wire.delta(previous, current)
    character.update(current)
    return packets
