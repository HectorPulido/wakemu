"""Original installed boat links; the caller owns the travel transaction.

Native aKq has arrival XY and map, but no altitude. Never treat clx (label ID)
as altitude. Require one authoritative walkable surface at the original XY.
"""
import json
import re
import struct
from functools import lru_cache

SETTING = "native_boat_contracts"


def load(db):
    """Read the complete boat authority from PostgreSQL; never use local files."""
    row = db.execute("SELECT value FROM settings WHERE name=%s", (SETTING,)).fetchone()
    if row is None:
        raise ValueError("Missing PostgreSQL native boat contracts")
    return validate(row["value"])


def validate(document):
    """Reject incomplete or ambiguous authority before exposing any route."""

    def integer(value, minimum=-(2**31), maximum=2**31 - 1):
        if type(value) is not int or not minimum <= value <= maximum:
            raise ValueError("Invalid native boat contract integer")

    if type(document) is not dict or set(document) != {
        "endpoints",
        "routes",
        "provenance",
    }:
        raise ValueError("Invalid native boat contract document")
    if type(document["provenance"]) is not dict:
        raise ValueError("Missing native boat provenance")
    endpoints, links, route_ids = {}, {}, set()
    for collection in ("endpoints", "routes"):
        if type(document[collection]) is not list or not document[collection]:
            raise ValueError("Missing native boat contract collection")
    for endpoint in document["endpoints"]:
        if type(endpoint) is not dict or set(endpoint) != {
            "id",
            "label_id",
            "map_id",
            "native_kind",
            "parameter",
            "source_position",
            "x",
            "y",
        }:
            raise ValueError("Invalid native boat endpoint")
        for key in ("id", "map_id", "label_id", "parameter"):
            integer(
                endpoint[key], -(2**31) if key in ("label_id", "parameter") else 1
            )
        for key in ("native_kind", "x", "y"):
            integer(endpoint[key])
        position = endpoint["source_position"]
        if type(position) is not dict or set(position) != {"x", "y", "z"}:
            raise ValueError("Invalid native boat source position")
        for coordinate in position.values():
            integer(coordinate)
        if endpoint["id"] in endpoints:
            raise ValueError("Duplicate native boat endpoint")
        endpoints[endpoint["id"]] = endpoint
    for route in document["routes"]:
        if type(route) is not dict or set(route) != {
            "id",
            "source",
            "destination",
            "source_criterion",
            "destination_criterion",
            "native_clV",
            "animation",
        }:
            raise ValueError("Invalid native boat route")
        integer(route["id"], 1)
        for key in ("source", "destination"):
            integer(route[key], 1)
            if route[key] not in endpoints:
                raise ValueError("Native boat route references missing endpoint")
        if (
            route["id"] in route_ids
            or route["source"] == route["destination"]
            or type(route["native_clV"]) is not bool
        ):
            raise ValueError("Duplicate or invalid native boat route")
        route_ids.add(route["id"])
        for key in ("source_criterion", "destination_criterion"):
            if type(route[key]) is not str or "\0" in route[key]:
                raise ValueError("Invalid native boat criterion")
        animation = route["animation"]
        if type(animation) is not dict or set(animation) != {
            "name",
            "duration_ms",
            "fade_in_ms",
            "fade_out_ms",
        }:
            raise ValueError("Invalid native boat animation")
        if (
            type(animation["name"]) is not str
            or not animation["name"]
            or "\0" in animation["name"]
        ):
            raise ValueError("Invalid native boat animation name")
        for key in ("duration_ms", "fade_in_ms", "fade_out_ms"):
            integer(animation[key], 0)
        links.setdefault(frozenset((route["source"], route["destination"])), []).append(
            route
        )
    # Detach authority from the connection's mutable JSON representation.
    return json.loads(json.dumps(document))


@lru_cache(maxsize=1)
def _indexes():
    from wakfu_server.storage.native_catalog import _database

    with _database().connection() as db:
        contracts = load(db)
    endpoints = {row["id"]: row for row in contracts["endpoints"]}
    links = {}
    for row in contracts["routes"]:
        links.setdefault(frozenset((row["source"], row["destination"])), []).append(row)
    return endpoints, links


def source(character, body):
    """Identify a current-map boat in csO13686 without authorizing movement."""
    if len(body) != 16:
        raise ValueError("Invalid native boat request")
    identity, _ = struct.unpack(">qq", body)
    endpoints, _ = _indexes()
    row = endpoints.get(identity)
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


def resolve(character, body, *, source_allowed, geometry, criterion_evaluator=None):
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
    endpoints, all_links = _indexes()
    destination = endpoints.get(destination_id)
    links = all_links.get(frozenset((source_id, destination_id)), ())
    if destination is None or source_id == destination_id or not links:
        raise ValueError("No native boat link between these endpoints")
    if not source_allowed(character, origin):
        raise ValueError("Native boat source authority denied")
    allowed = criterion_allowed if criterion_evaluator is None else criterion_evaluator
    eligible = [
        row
        for row in links
        if all(
            allowed(row[key], character)
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
    endpoints, _ = _indexes()
    original = endpoints.get(origin.get("id"))
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
