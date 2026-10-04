"""Installed native environment states, independent of captured account data.

13984 updates existing bEG objects (cEX); it cannot spawn missing objects.
Send only after the client's environment loader has registered the current map.
"""
from .paths import DATA_ROOT
import json
import struct
from collections import defaultdict
from pathlib import Path

_ROWS = json.loads((DATA_ROOT / "native-map-objects.json").read_text())
_MAPS = defaultdict(dict)
for _row in _ROWS:
    _existing = _MAPS[_row["map_id"]].get(_row["id"])
    if _existing is not None and _existing != _row:
        raise ValueError("Conflicting native interactive object identity")
    _MAPS[_row["map_id"]][_row["id"]] = _row
_ACTIONS = json.loads((DATA_ROOT / "interactive-actions.json").read_text())


def objects(map_id):
    """Return copies so callers cannot mutate the installed native baseline."""
    return tuple(dict(row) for row in _MAPS.get(map_id, {}).values())


def snapshots(map_id):
    """13984 bodies preserving native state; batches respect signed-short counts."""
    rows = objects(map_id)
    result = []
    for offset in range(0, len(rows), 32767):
        chunk = rows[offset : offset + 32767]
        body = bytearray(struct.pack(">h", len(chunk)))
        for row in chunk:
            payload = bytes.fromhex(row["payload_hex"])
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
