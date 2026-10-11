"""Installed native environment states, independent of captured account data.

13984 updates existing bEG objects (cEX); it cannot spawn missing objects.
Send only after the client's environment loader has registered the current map.
"""
from wakfu_server import native_catalog as protocol_catalog
from .paths import DATA_ROOT
import hashlib
import json
import struct
from collections import defaultdict
from pathlib import Path

_ROWS = protocol_catalog.load(DATA_ROOT / "native-map-objects.json")
_MAPS = defaultdict(dict)
for _row in _ROWS:
    _existing = _MAPS[_row["map_id"]].get(_row["id"])
    if _existing is not None and _existing != _row:
        raise ValueError("Conflicting native interactive object identity")
    _MAPS[_row["map_id"]][_row["id"]] = _row
_ACTIONS = protocol_catalog.load(DATA_ROOT / "interactive-actions.json")
# Official exterior entrance 13984: field 2, state 1, visible/usable, bh=true.
# Base fields 0/1/3 describe installed geometry; they do not hydrate field 2.
_DUNGEON_ENTRY_STATE = bytes.fromhex("01020000000602000101010000010000000000")
# Every object's state is decoded through the installed client's own bEE/bEG
# classes, preserving hidden/disabled states, auxiliary flags, and actions.
_STATE_CATALOG = protocol_catalog.load(DATA_ROOT / "native-interactive-states.json")
if (
    _STATE_CATALOG["baseline_sha256"]
    != hashlib.sha256(
        protocol_catalog.read_bytes(DATA_ROOT / "native-map-objects.json")
    ).hexdigest()
):
    raise ValueError("Native interactive states belong to a different baseline")
_DYNAMIC_STATES = {}
for _state_row in _STATE_CATALOG["objects"]:
    _key = (_state_row["map_id"], _state_row["id"])
    _native_row = _MAPS.get(_key[0], {}).get(_key[1])
    if (
        _native_row is None
        or _native_row["type"] != _state_row["type"]
        or _key in _DYNAMIC_STATES
    ):
        raise ValueError("Conflicting native dynamic object identity")
    _DYNAMIC_STATES[_key] = bytes.fromhex(_state_row["payload_hex"])
if set(_DYNAMIC_STATES) != {
    (map_id, identity) for map_id, rows in _MAPS.items() for identity in rows
}:
    raise ValueError("Incomplete native dynamic object states")


def objects(map_id):
    """Return copies so callers cannot mutate the installed native baseline."""
    return tuple(dict(row) for row in _MAPS.get(map_id, {}).values())


def snapshots(map_id, *, position=None):
    """Hydrate evidenced installed objects on every map load and replay."""
    if position is not None:
        from wakfu_server.world_scene_sync import chunk, neighborhood, dynamic_snapshots

        # Native cdE/bEC only register the interactive loader's 3x3 neighborhood.
        # Far-map definitions cannot accept 13984 and otherwise log failed spawn
        # errors. Keep all nearby states and the existing delayed replay policy;
        # successful socket delivery does not acknowledge client attachment.
        return dynamic_snapshots(map_id, neighborhood(chunk(position)))
    from wakfu_server.dungeon_instances import entry_object_ids

    rows = objects(map_id)
    entrances = entry_object_ids(map_id)
    dynamic_rows = tuple(
        {
            "id": row["id"],
            "payload_hex": (
                _DUNGEON_ENTRY_STATE
                if row["id"] in entrances
                else _DYNAMIC_STATES[(map_id, row["id"])]
            ).hex(),
        }
        for row in rows
    )
    # bEC reconstructs each object from the installed raw asset before applying
    # this state. Sending a separate baseline first attaches an unhydrated
    # instance which the native scene registry refuses to replace later.
    return _snapshot_bodies(dynamic_rows)


def _snapshot_bodies(rows, entrance_ids=frozenset()):
    result = []
    for offset in range(0, len(rows), 32767):
        chunk = rows[offset : offset + 32767]
        body = bytearray(struct.pack(">h", len(chunk)))
        for row in chunk:
            payload = (
                _DUNGEON_ENTRY_STATE
                if row["id"] in entrance_ids
                else bytes.fromhex(row["payload_hex"])
            )
            if len(payload) > 32767:
                raise ValueError("Native interactive payload exceeds codec limit")
            body.extend(struct.pack(">qh", row["id"], len(payload)))
            body.extend(payload)
        result.append(bytes(body))
    return tuple(result)


def interaction(character, body):
    """Decode cpF/12870 without treating every action as transport discovery.

    Classification is not permission to execute an action. Native access rules,
    owned state and action-specific responses must be validated by its handler.
    """
    if len(body) != 12:
        raise ValueError("Invalid interactive request length")
    identity, action, parameter = struct.unpack(">qHH", body)
    row = _MAPS.get(character["map_id"], {}).get(identity)
    if character.get("instance_id", 0) != 0 or row is None:
        raise ValueError("Unknown interactive object in current map instance")
    name = _ACTIONS.get(str(action))
    if name is None:
        raise ValueError("Unknown native interactive action")
    route = "unsupported"
    if row["type"] in ("Zaap", "Drago"):
        route = (
            "transport_registration"
            if name == "REGISTER"
            else "transport_menu"
            if name == "ACTIVATE"
            else "unsupported"
        )
    elif row["type"] == "Door":
        route = "door_state"
    elif row["type"] == "Teleporter":
        route = "teleporter"
    return {
        "id": identity,
        "type": row["type"],
        "action_id": action,
        "action": name,
        "parameter": parameter,
        "route": route,
        "map_id": row["map_id"],
        "x": row["x"],
        "y": row["y"],
        "z": row["z"],
    }
