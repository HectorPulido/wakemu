"""Original installed boat links; the caller owns the travel transaction.

Native aKq has arrival XY and map, but no altitude. Never treat clx (label ID)
as altitude. Require one authoritative walkable surface at the original XY.
"""
import gzip
import json
import re
import struct
from pathlib import Path

_CONTRACTS = json.loads(
    gzip.decompress(
        Path(__file__).with_name("native_boat_contracts.json.gz").read_bytes()
    )
)
_ENDPOINTS = {row["id"]: row for row in _CONTRACTS["endpoints"]}
_LINKS = {}
for _row in _CONTRACTS["routes"]:
    _LINKS.setdefault(frozenset((_row["source"], _row["destination"])), []).append(_row)


def source(character, body):
    """Identify a current-map boat in csO13686 without authorizing movement."""
    if len(body) != 16:
        raise ValueError("Invalid native boat request")
    identity, _ = struct.unpack(">qq", body)
    row = _ENDPOINTS.get(identity)
    if row is None or row["map_id"] != character["map_id"]:
        return None
    return json.loads(json.dumps(row))


def criterion_allowed(expression, character):
    """Support only unconditional and exact real-level gates; unknown fails closed."""
    expression = expression.strip()
    if not expression:
        return True
    match = re.fullmatch(r"GetRealLevel\(\)\s*>=\s*(\d+)", expression)
    if match is None:
        return False
    level = character.get("level")
    return type(level) is int and level >= int(match[1])


def resolve(character, body, *, source_allowed, geometry):
    """Resolve native csO13686 with mandatory source authority and map geometry.

    source_allowed(character, original_endpoint) validates authoritative live
    position, occupation, ownership and lease. geometry(map_id) returns the
    current native edge dictionary. The caller must commit through its existing
    fenced transition_map transaction and perform normal world/bootstrap cleanup.
    """
    origin = source(character, body)
    if origin is None or character.get("instance_id", 0) != 0:
        raise ValueError("Unknown native boat in current public map")
    source_id, destination_id = struct.unpack(">qq", body)
    destination = _ENDPOINTS.get(destination_id)
    links = _LINKS.get(frozenset((source_id, destination_id)), ())
    if destination is None or source_id == destination_id or not links:
        raise ValueError("No native boat link between these endpoints")
    if not source_allowed(character, origin):
        raise ValueError("Native boat source authority denied")
    eligible = [
        row
        for row in links
        if all(
            criterion_allowed(row[key], character)
            for key in ("source_criterion", "destination_criterion")
        )
    ]
    if not eligible:
        raise ValueError("Native boat access criterion is unsupported or unmet")
    # The native client accepts any matching eligible link (fzD.aQ/bRm.a).
    link = min(eligible, key=lambda row: row["id"])
    edges = geometry(destination["map_id"])["edges"]
    surfaces = {
        tuple(cell)
        for edge in edges
        for cell in edge
        if tuple(cell[:2]) == (destination["x"], destination["y"])
    }
    if len(surfaces) != 1:
        raise ValueError("Native boat arrival altitude is not uniquely walkable")
    x, y, z = surfaces.pop()
    return {
        "source_id": source_id,
        "destination_id": destination_id,
        "native_link_id": link["id"],
        "destination": {
            "map_id": destination["map_id"],
            "instance_id": 0,
            "x": x,
            "y": y,
            "z": z,
        },
        "animation": dict(link["animation"]),
    }


def admit_source(store, account_id, generation, character, origin, *, blocked=False):
    """Fence an owned selected actor and the original public boat position.

    Existing transition_map compares the same complete SQL source once more
    during commit. The four-step, one-height proximity rule is existing local
    environment policy, not an inferred native bEu activation range.
    """
    import math

    from wakfu_server.environment_interactions import _guard, _position
    from wakfu_server.inventory_items import _lease

    if blocked:
        raise ValueError("Boat travel is unavailable during an occupation")
    original = _ENDPOINTS.get(origin.get("id"))
    if original is None or origin != original:
        raise ValueError("Boat source differs from installed native definition")
    for axis in ("x", "y", "z"):
        if type(character.get(axis)) not in (int, float) or not math.isfinite(
            character[axis]
        ):
            raise ValueError("Invalid native boat source position")
    _position(character, dict(original["source_position"], map_id=original["map_id"]))
    with store.connection() as db:
        _lease(store, db, account_id, generation, character["id"])
        _guard(db, character["id"])
        saved = store.character(account_id, character["id"], db)
        if any(
            saved[key] != character[key]
            for key in ("map_id", "instance_id", "x", "y", "z", "level")
        ):
            raise ValueError("Native boat source is desynchronized")
    return True
