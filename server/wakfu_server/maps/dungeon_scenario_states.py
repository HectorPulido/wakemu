"""Explicit scenario-owned native marker states, using existing state hydration/wire.

Scenario ownership is separate from combat removal events. No synthetic eHQ
removal ID, inventory key, duration, or stat contribution is invented here.
"""
from psycopg.types.json import Jsonb
from wakfu_server import consumable_buffs


def grant(store, db, character_id, *, instance_id, rule_sha256, source_uid, descriptor):
    consumable_buffs._context(store, db, character_id, None)
    if (
        any(type(value) is not int or value <= 0 for value in (instance_id, source_uid))
        or not isinstance(rule_sha256, str)
        or len(rule_sha256) != 64
        or type(descriptor.get("source_item_reference")) is not int
        or descriptor["source_item_reference"] <= 0
    ):
        raise ValueError("Invalid scenario-owned state source")
    identity = descriptor.get("state_id")
    if (
        type(identity) is not int
        or not 0 < identity <= 32767
        or descriptor.get("maximum_level") != 1
        or descriptor.get("native_realtime_duration_base") != -1
        or descriptor.get("native_marker_generic") != 400
        or type(descriptor.get("native_marker_effect_id")) is not int
        or descriptor["native_marker_effect_id"] <= 0
        or not descriptor.get("source_sha256")
    ):
        raise ValueError("Unqualified native scenario state descriptor")
    existing = db.execute(
        "SELECT uid FROM character_consumable_buffs WHERE character_id=%s AND state_id=%s FOR UPDATE",
        (character_id, identity),
    ).fetchone()
    if existing is not None:
        raise ValueError("Native key state already exists outside this attempt")
    state = dict(
        state_id=identity,
        level=1,
        clock="event",
        duration_ms=0,
        maximum_level=1,
        stacking="reject_duplicate",
        effect_ids=[],
        metadata=dict(
            native_realtime_duration_base=-1,
            scenario_lifecycle=dict(instance_id=instance_id, rule_sha256=rule_sha256),
            native_marker_effect_id=descriptor["native_marker_effect_id"],
            native_marker_generic=400,
            source_sha256=descriptor["source_sha256"],
        ),
    )
    row = db.execute(
        "INSERT INTO character_consumable_buffs(character_id,state_id,level,source_item_ref,source_item_uid,clock,duration_ms,remaining_ms,expires_ms,online_generation,online_anchor_ms,metadata) "
        "VALUES(%s,%s,1,%s,%s,'event',0,0,NULL,NULL,NULL,%s) RETURNING uid",
        (
            character_id,
            identity,
            descriptor["source_item_reference"],
            source_uid,
            Jsonb(state),
        ),
    ).fetchone()
    return row["uid"]


def consume(store, db, character_id, *, uid, instance_id, rule_sha256):
    consumable_buffs._context(store, db, character_id, None)
    row = db.execute(
        "SELECT * FROM character_consumable_buffs WHERE uid=%s AND character_id=%s FOR UPDATE",
        (uid, character_id),
    ).fetchone()
    if row is None or row["metadata"].get("metadata", {}).get(
        "scenario_lifecycle"
    ) != dict(instance_id=instance_id, rule_sha256=rule_sha256):
        raise ValueError("Native scenario key carrier changed")
    consumable_buffs.retire_states(store, db, character_id, uids=(uid,))
