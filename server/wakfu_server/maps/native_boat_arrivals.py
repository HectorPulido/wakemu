"""Original Boat arrival-only columns, with native directed departures.

Nonwalkable landing columns remain excluded from ordinary terrain admission.
This policy preserves a server-authoritative native POSITION and permits only
its independently recovered native Sm egress; it never creates an incoming edge.
"""
import hashlib
import json
from functools import lru_cache

SETTING = "native_boat_arrival_authority"
POLICY = "wakemu.native-boat-original-column-source-only-v1"


def _hash(value):
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode()
    ).hexdigest()


def _point(value):
    if (
        not isinstance(value, (list, tuple))
        or len(value) != 3
        or any(type(n) is not int for n in value)
        or not -512 <= value[2] <= 511
    ):
        raise ValueError("Invalid native Boat arrival coordinate")
    return tuple(value)


def load(db):
    """Validate source data against the current immutable catalog and Boat table."""
    row = db.execute("SELECT value FROM settings WHERE name=%s", (SETTING,)).fetchone()
    if row is None:
        return ()
    value = row["value"]
    if (
        not isinstance(value, dict)
        or set(value)
        != {
            "schema_version",
            "policy",
            "catalog_revision",
            "client_sha256",
            "source_authority",
            "arrivals",
        }
        or value["schema_version"] != 1
        or type(value["schema_version"]) is not int
        or value["policy"] != POLICY
        or not value["source_authority"]
        or len(value["client_sha256"]) != 64
        or not isinstance(value["arrivals"], list)
    ):
        raise ValueError("Invalid original Boat arrival authority")
    from wakfu_server import native_catalog
    from wakfu_server.native_catalog_compatibility import require_source_revision

    revision = native_catalog.release()
    pinned = value["catalog_revision"]
    if (
        type(pinned) is not str
        or len(pinned) != 64
        or any(char not in "0123456789abcdef" for char in pinned)
    ):
        raise ValueError("Invalid Boat arrival source catalog")
    dependencies = set()
    for entry in value["arrivals"]:
        if (
            not isinstance(entry, dict)
            or type(entry.get("map_id")) is not int
            or not 0 < entry["map_id"] < 2**31
        ):
            raise ValueError("Invalid native Boat arrival record")
        dependencies.add(f"combat-maps/{entry['map_id']}.json")
    if dependencies:
        # Boat endpoints/routes are the independently checked DB contract
        # below. Only these native map documents are read from the catalog;
        # topology_sha256 is the original map JAR hash, not a JSON checksum.
        require_source_revision(pinned, tuple(sorted(dependencies)))
    elif pinned != revision:
        raise ValueError("Boat arrival source catalog changed")
    if native_catalog.release() != revision:
        raise ValueError("Boat arrival catalog changed during validation")
    from . import native_boats

    contracts = native_boats.load(db)
    if value["client_sha256"] != contracts["provenance"].get("client_sha256"):
        raise ValueError("Boat arrival original client authority changed")
    endpoints = {row["id"]: row for row in contracts["endpoints"]}
    linked = {
        link[key] for link in contracts["routes"] for key in ("source", "destination")
    }
    result, seen = [], set()
    for entry in value["arrivals"]:
        if not isinstance(entry, dict) or set(entry) != {
            "endpoint_id",
            "endpoint_sha256",
            "map_id",
            "source",
            "surface_count",
            "surface_bLD",
            "surface_bLE",
            "surface_bLF",
            "surface_aYX",
            "geometry_sha256",
            "topology_sha256",
            "proof_sha256",
            "native_departures",
        }:
            raise ValueError("Invalid native Boat arrival record")
        if entry["proof_sha256"] != _hash(
            {k: v for k, v in entry.items() if k != "proof_sha256"}
        ):
            raise ValueError("Boat arrival source proof changed")
        endpoint = endpoints.get(entry["endpoint_id"])
        source = _point(entry["source"])
        if (
            entry["endpoint_id"] in seen
            or entry["endpoint_id"] not in linked
            or endpoint is None
            or _hash(endpoint) != entry["endpoint_sha256"]
            or endpoint["map_id"] != entry["map_id"]
            or (endpoint["x"], endpoint["y"]) != source[:2]
            or entry["surface_count"] != 1
            or entry["surface_bLD"] != -1
            or any(
                type(entry[k]) is not int
                for k in (
                    "surface_count",
                    "surface_bLD",
                    "surface_bLE",
                    "surface_bLF",
                    "surface_aYX",
                )
            )
            or any(
                not isinstance(entry[k], str) or len(entry[k]) != 64
                for k in ("geometry_sha256", "topology_sha256", "proof_sha256")
            )
        ):
            raise ValueError(
                "Boat arrival differs from its original linked endpoint/column"
            )
        with native_catalog._database().connection() as source_db:
            manifest = source_db.execute(
                "SELECT sha256 FROM native_catalog_documents WHERE revision=%s AND path=%s",
                (revision, f"combat-maps/{entry['map_id']}.json"),
            ).fetchone()
        if manifest is None or manifest["sha256"] != entry["geometry_sha256"]:
            raise ValueError("Boat arrival terrain source changed")
        departures = entry["native_departures"]
        if not isinstance(departures, list) or not departures:
            raise ValueError("Boat arrival has no recovered native departure")
        targets = set()
        for departure in departures:
            if (
                not isinstance(departure, dict)
                or set(departure) != {"target", "target_bLD"}
                or type(departure["target_bLD"]) is not int
                or departure["target_bLD"] < 0
            ):
                raise ValueError(
                    "Boat arrival departure lacks a walkable native target"
                )
            target = _point(departure["target"])
            if (
                target in targets
                or sum(abs(a - b) for a, b in zip(source[:2], target[:2])) != 1
            ):
                raise ValueError("Boat arrival departure is duplicate or not cardinal")
            targets.add(target)
        seen.add(entry["endpoint_id"])
        result.append(dict(entry, source=source, targets=frozenset(targets)))
    if native_catalog.release() != revision:
        raise ValueError("Boat arrival catalog changed during validation")
    return tuple(result)


@lru_cache(maxsize=1)
def _authority():
    from wakfu_server.storage.native_catalog import _database

    with _database().connection() as db:
        return load(db)


def arrival(destination, geometry):
    """Return the exact native height only for an authenticated source-only column."""
    for entry in _authority():
        if entry["endpoint_id"] != destination["id"]:
            continue
        if (
            entry["map_id"] != destination["map_id"]
            or entry["source"][:2] != (destination["x"], destination["y"])
            or _hash(destination) != entry["endpoint_sha256"]
            or geometry.get("map_id") != entry["map_id"]
        ):
            raise ValueError("Boat arrival endpoint or terrain identity changed")
        cells = {tuple(p) for p in geometry["cells"]}
        if entry["source"] in cells or not entry["targets"].issubset(cells):
            raise ValueError("Boat source-only arrival changed its terrain membership")
        if any(tuple(target) == entry["source"] for _, target in geometry["edges"]):
            raise ValueError(
                "Boat source-only arrival acquired an ordinary incoming edge"
            )
        return entry["source"]
    return None


def validate_movement(character, request, *, geometry):
    """Validate arrival-only points after the ordinary approved-path identity guard."""
    if character.get("instance_id", 0) != 0:
        return
    entries = [row for row in _authority() if row["map_id"] == character["map_id"]]
    if not entries:
        return
    sources = {row["source"]: row for row in entries}
    point = tuple(request["start_position"][axis] for axis in ("x", "y", "z"))
    checked = False
    for step in request["steps"]:
        target = tuple(
            point[i] + step["d" + axis] for i, axis in enumerate(("x", "y", "z"))
        )
        if target in sources:
            raise ValueError(
                "Native Boat arrival is not an ordinary movement destination"
            )
        if point in sources:
            entry = sources[point]
            if not checked:
                base = geometry(character["map_id"])
                if base.get("map_id") != character["map_id"] or not entry[
                    "targets"
                ].issubset({tuple(p) for p in base["cells"]}):
                    raise ValueError("Native Boat departure terrain changed")
                checked = True
            if target not in entry["targets"]:
                raise ValueError(
                    "Movement does not follow an original native Boat departure"
                )
        point = target
