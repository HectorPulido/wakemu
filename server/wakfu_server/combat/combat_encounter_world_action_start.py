"""Reviewed native NPC world actions entering the existing combat pipeline.

The original server-side producer is unavailable. Explicit source-sealed scene
policy binds the native action to a pinned ordinary encounter; it never removes
world properties, changes the roster, or grants a spell/resource/state.
"""
from collections import Counter
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import struct

_POLICY_SHA256 = "f5a73216536283a752b68b3fd9041b23a55c3288bd93307b61b4551d8515717d"
_AUTHORITY = "authorized_wakemu_native_encounter_action_reconstruction"


def _digest(value):
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode()
    ).hexdigest()


@lru_cache(maxsize=1)
def _policies():
    raw = Path(__file__).with_name("native_encounter_world_actions.json").read_bytes()
    if hashlib.sha256(raw).hexdigest() != _POLICY_SHA256:
        raise ValueError("Native encounter world-action policy changed")
    value = json.loads(raw)
    if (
        value.get("schema_version") != 1
        or value.get("policy") != "source-qualified-native-encounter-world-action-v1"
        or value.get("authority") != _AUTHORITY
    ):
        raise ValueError("Unknown native encounter world-action policy")
    return value


def recognized_route(route_key):
    return any(row["route_key"] == route_key for row in _policies()["scopes"])


def _native_source(reference):
    from wakfu_server import native_catalog
    from wakfu_server.paths import DATA_ROOT

    return native_catalog.record(
        DATA_ROOT / "monster-encyclopedia.json", "monsters", str(reference)
    )


def admit_records(
    character,
    body,
    *,
    instance,
    progress,
    membership,
    spawn,
    group,
    config,
    native_source=None
):
    """Pure admission over actual leased-scene and frozen native records.

    Nondeclared routes remain ordinary NPC interactions. Recognized encounter
    requests fail closed on stale ownership, room, actor, roster or source.
    The serving caller still claims the real group in the common fight path.
    """
    if not recognized_route(instance.get("context_route_key")):
        return None
    if type(body) is not bytes or len(body) != 16:
        raise ValueError("Invalid native encounter action payload")
    target_id, action_id = struct.unpack(">qq", body)
    if target_id >= 0 or not 0 < action_id < 2**31:
        raise ValueError("Invalid native encounter action identity")
    if (
        not isinstance(config, dict)
        or not isinstance(config.get("route"), dict)
        or not isinstance(config.get("compiled_plan"), dict)
        or not isinstance(config.get("evidence_hashes"), dict)
        or type(config.get("version")) is not int
        or type(config["compiled_plan"].get("document_sha256")) is not str
        or not isinstance(config["compiled_plan"].get("rooms"), list)
    ):
        raise ValueError("Native encounter action configuration is absent or malformed")
    identity = character["instance_id"]
    if (
        instance.get("status") != "active"
        or instance.get("instance_id") != identity
        or progress.get("instance_id") != identity
        or progress.get("status") != "active"
        or instance.get("party_id") != progress.get("party_id")
        or membership.get("status") != "active"
        or membership.get("instance_id") != identity
        or membership.get("party_id") != instance.get("party_id")
        or membership.get("character_id") != character["id"]
        or config["route"]["key"] != instance["context_route_key"]
        or config["version"] != instance["context_policy_version"]
    ):
        raise ValueError("Native encounter action has stale dungeon ownership")
    from wakfu_server.dungeon_runtime_config import canonical_hash

    if canonical_hash(config["compiled_plan"]) != config["evidence_hashes"]["plan"]:
        raise ValueError("Native encounter action has a changed frozen plan")
    scopes = [
        r
        for r in _policies()["scopes"]
        if r["route_key"] == instance["context_route_key"]
        and r["plan_sha256"] == config["evidence_hashes"]["plan"]
        and r["document_sha256"] == progress.get("catalog_hash")
        and r["document_sha256"] == config["compiled_plan"]["document_sha256"]
    ]
    if len(scopes) != 1:
        raise ValueError("Native encounter action lacks its reviewed source scope")
    key = (character["map_id"], identity, spawn.get("group_id"))
    if (
        spawn.get("instance_id") != identity
        or spawn.get("room_order") != progress.get("current_room")
        or spawn.get("asset_map_id") != character["map_id"]
        or tuple(group.get("key", ())) != key
        or group.get("status", "available") != "available"
    ):
        raise ValueError("Native encounter action has a stale room group")
    rooms = [r for r in progress["rooms"] if r["order"] == progress["current_room"]]
    planned = [
        r
        for r in config["compiled_plan"]["rooms"]
        if r["order"] == progress["current_room"]
    ]
    if len(rooms) != 1 or len(planned) != 1:
        raise ValueError("Native encounter action room is absent")
    expected = Counter({})
    for row in rooms[0]["monsters"]:
        expected[row["ref_id"]] += row["count"]
    planned_counts = Counter({})
    for row in planned[0]["monsters"]:
        planned_counts[row["ref_id"]] += row["count"]
    members = group.get("members", ())
    if (
        not members
        or expected != planned_counts
        or Counter(m["ref"] for m in members) != expected
        or len({m["id"] for m in members}) != len(members)
        or any(
            m.get("map_id") != key[0]
            or m.get("instance_id") != identity
            or m.get("environmental_world_action_only") is not None
            for m in members
        )
    ):
        raise ValueError("Native encounter action roster differs from its pinned room")
    targets = [m for m in members if m["id"] == target_id]
    if len(targets) != 1:
        raise ValueError("Native encounter action target is absent")
    target = targets[0]
    rules = [
        r
        for r in scopes[0]["actions"]
        if r["monster_reference"] == target["ref"] and r["action_id"] == action_id
    ]
    if len(rules) != 1:
        raise ValueError("Native encounter action is not declared for this actor")
    source = (native_source or _native_source)(target["ref"])
    if not isinstance(source, dict) or source.get("ref") != target["ref"]:
        raise ValueError("Native encounter action breed source is absent")
    actions = [r for r in source.get("world_actions", ()) if r.get("d") == action_id]
    if len(actions) != 1:
        raise ValueError("Native encounter action source is absent or ambiguous")
    action = actions[0]
    properties = source.get("raw_native", {}).get("csc")
    source_digest = _digest(
        dict(
            monster_reference=target["ref"], world_properties=properties, action=action
        )
    )
    if (
        source_digest != rules[0]["native_source_sha256"]
        or 13 not in properties
        or action.get("aGJ") != 1
        or action.get("clT") != ""
        or action.get("getDuration") != 0
    ):
        raise ValueError("Native encounter world-action source changed")
    from wakfu_server.objectives.environmental_monster_actions import (
        native_action_response,
    )

    return dict(
        target_id=target_id,
        action_id=action_id,
        group_key=key,
        position=tuple(target[k] for k in ("x", "y", "z")),
        authority=_AUTHORITY,
        source_sha256=source_digest,
        native_response=native_action_response(target_id, character["id"], action_id),
    )


def prepare(store, character, body, group):
    """Read only durable current membership and exact pinned room ownership."""
    if type(body) is not bytes or len(body) != 16 or not character.get("instance_id"):
        return None
    with store.connection() as db:
        instance = db.execute(
            "SELECT * FROM dungeon_instances WHERE instance_id=%s",
            (character["instance_id"],),
        ).fetchone()
        if instance is None or not recognized_route(instance.get("context_route_key")):
            return None
        progress = db.execute(
            "SELECT * FROM dungeon_room_runs WHERE instance_id=%s",
            (character["instance_id"],),
        ).fetchone()
        membership = db.execute(
            "SELECT * FROM dungeon_instance_members WHERE instance_id=%s "
            "AND character_id=%s",
            (character["instance_id"], character["id"]),
        ).fetchone()
        spawn = db.execute(
            "SELECT * FROM dungeon_room_spawn_receipts WHERE instance_id=%s "
            "AND room_order=%s",
            (character["instance_id"], (progress or {}).get("current_room")),
        ).fetchone()
        row = db.execute(
            "SELECT configuration FROM dungeon_runtime_configurations "
            "WHERE route_key=%s AND policy_version=%s",
            (instance["context_route_key"], instance["context_policy_version"]),
        ).fetchone()
        return admit_records(
            character,
            body,
            instance=instance,
            progress=progress or {},
            membership=membership or {},
            spawn=spawn or {},
            group=group,
            config={} if row is None else row["configuration"],
        )
