"""Mining approach authority from published native world exploration geometry.

This catalog validates native profession adjacency independently of combat movement.
Missing or malformed native evidence fails closed; no filesystem fallback exists.
"""
from wakfu_server import native_catalog
from .paths import DATA_ROOT
from functools import lru_cache
import hashlib
import json
import os

PROFILE = "native_world_exploration_4_0_6"


def _position(value):
    if (
        not isinstance(value, (tuple, list))
        or len(value) != 3
        or any(type(component) is not int for component in value)
    ):
        raise ValueError("Invalid native mining navigation position")
    return tuple(value)


def _incoming(document, map_id):
    if not isinstance(document, dict) or document.get("map_id") != map_id:
        raise ValueError("Native world navigation map mismatch")
    provenance = document.get("provenance")
    if document.get("profile") != PROFILE or not isinstance(provenance, dict):
        raise ValueError("Unproven native world exploration profile")
    if provenance.get("source") != "installed-client" or any(
        not isinstance(provenance.get(key), str)
        or len(provenance[key]) != 64
        or any(c not in "0123456789abcdef" for c in provenance[key])
        for key in ("client_sha256", "topology_sha256")
    ):
        raise ValueError("Native world navigation provenance is required")
    if provenance.get("approach_authority") != "cWn.gu:VF.a:profession73":
        raise ValueError("Native mineral approach evidence is required")
    if not isinstance(document.get("cells"), list) or not isinstance(
        document.get("resource_approaches"), list
    ):
        raise ValueError("Invalid native world navigation geometry")
    cells = {_position(row) for row in document["cells"]}
    incoming = {}
    for row in document["resource_approaches"]:
        if not isinstance(row, dict) or set(row) != {
            "position",
            "approaches",
            "ground_id",
            "eligible_refs",
        }:
            raise ValueError("Invalid native mineral approach record")
        if (
            type(row["ground_id"]) is not int
            or row["ground_id"] < 0
            or (
                not isinstance(row["eligible_refs"], list)
                or any(type(ref) is not int or ref <= 0 for ref in row["eligible_refs"])
            )
        ):
            raise ValueError("Invalid native mineral ground evidence")
        destination = _position(row["position"])
        if destination in incoming or not isinstance(row["approaches"], list):
            raise ValueError("Duplicate or malformed native mineral approach")
        sources = set()
        for value in row["approaches"]:
            source = _position(value)
            if source not in cells:
                raise ValueError("Native mining approach leaves walkable surfaces")
            if abs(source[0] - destination[0]) + abs(source[1] - destination[1]) != 1:
                raise ValueError("Native mining approach must be cardinal adjacent")
            sources.add(source)
        incoming[destination] = {
            "ground_id": row["ground_id"],
            "eligible_refs": frozenset(row["eligible_refs"]),
            "approaches": frozenset(sources),
        }
    return incoming


@lru_cache(maxsize=32)
def _map_index(revision, map_id):
    path = DATA_ROOT / "world-navigation" / f"{map_id}.json"
    if os.environ.get("WAKFU_MINING_CATALOG_REVISION"):
        if len(revision) != 64 or any(c not in "0123456789abcdef" for c in revision):
            raise ValueError("Invalid pinned mining navigation revision")
        with native_catalog._database().connection() as db:
            row = db.execute(
                "SELECT d.raw,d.sha256 FROM native_catalog_documents d "
                "JOIN native_catalog_releases r USING(revision) "
                "WHERE d.revision=%s AND d.path=%s AND r.complete",
                (revision, f"world-navigation/{map_id}.json"),
            ).fetchone()
        if row is None:
            raise ValueError("Published native world navigation is unavailable")
        raw = bytes(row["raw"])
        if hashlib.sha256(raw).hexdigest() != row["sha256"]:
            raise ValueError("Native mining navigation checksum mismatch")
        return _incoming(json.loads(raw), map_id)
    if not native_catalog.exists(path):
        raise ValueError("Published native world navigation is unavailable")
    return _incoming(native_catalog.load(path), map_id)


def _revision():
    """Pin mining geometry independently of the unchanged gameplay catalog."""
    return os.environ.get("WAKFU_MINING_CATALOG_REVISION") or native_catalog.release()


def approaches(map_id, position):
    """Return verified adjacent source surfaces that can approach this vein."""
    if type(map_id) is not int or not 0 < map_id < 2**31:
        raise ValueError("Invalid mining navigation map")
    position = _position(position)
    return (
        _map_index(_revision(), map_id).get(position, {}).get("approaches", frozenset())
    )


def surface(map_id, x, y, z):
    """Return published native ground and species eligibility for a vein surface."""
    if type(map_id) is not int or not 0 < map_id < 2**31:
        raise ValueError("Invalid mining navigation map")
    position = _position((x, y, z))
    result = _map_index(_revision(), map_id).get(position)
    if result is None:
        raise ValueError("Unknown native mining surface")
    return dict(result)


def validate_placement(map_id, position):
    if not approaches(map_id, position):
        raise ValueError("Mining placement has no native world harvesting approach")


def reachable(character, resource):
    """Harvest only from a native neighboring approach, at the same instance."""
    if any(character[key] != resource[key] for key in ("map_id", "instance_id")):
        return False
    source = tuple(character[key] for key in ("x", "y", "z"))
    target = tuple(resource[key] for key in ("x", "y", "z"))
    return source in approaches(character["map_id"], target)
