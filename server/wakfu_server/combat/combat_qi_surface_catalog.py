"""Verified published native QI surface data; no private staging fallback."""
from wakfu_server import native_catalog as protocol_catalog
import hashlib
import json
from functools import lru_cache
from pathlib import Path

from wakfu_server.paths import DATA_ROOT
from .combat_qi_surfaces import NativeQISurfaces


@lru_cache(maxsize=1)
def _publication():
    directory = DATA_ROOT / "native-qi-surfaces"
    try:
        publication = protocol_catalog.load(directory / "publication.json")
        raw = protocol_catalog.read_bytes(directory / "manifest.json")
    except (OSError, ValueError) as error:
        raise ValueError("Missing published native QI surface catalog") from error
    manifest_hash = hashlib.sha256(raw).hexdigest()
    if (
        publication.get("schema") != "native-QI-surface-publication-v1"
        or publication.get("manifest_sha256") != manifest_hash
    ):
        raise ValueError("Published native QI surface manifest checksum mismatch")
    manifest = json.loads(raw)
    records = {}
    for row in manifest.get("maps", ()):
        identity = row.get("map_id")
        if identity is None and row.get("status") == "error":
            try:
                identity = int(Path(row["map"]).stem)
            except (KeyError, TypeError, ValueError) as error:
                raise ValueError("Invalid failed native QI map identity") from error
        if type(identity) is not int or identity <= 0 or identity in records:
            raise ValueError("Invalid or duplicate native QI catalog map identity")
        if row.get("status") not in ("exported", "error"):
            raise ValueError("Unknown native QI catalog map status")
        records[identity] = row
    exported = sum(row["status"] == "exported" for row in records.values())
    failed = len(records) - exported
    counts = publication.get("counts", {})
    if counts.get("imported") != exported or counts.get("failed_native") != failed:
        raise ValueError("Published native QI catalog count mismatch")
    return directory, records, manifest_hash


def native_qi_surface_provenance(map_id):
    if type(map_id) is not int or map_id <= 0:
        raise ValueError("Invalid native QI surface map identity")
    _, records, manifest_hash = _publication()
    row = records.get(map_id)
    if row is None:
        raise ValueError("No native QI surface export for requested map")
    if row["status"] != "exported":
        raise ValueError("Native QI surface decoding failed for requested map")
    result = dict(
        map_id=map_id,
        source_sha256=row.get("source_sha256"),
        output_sha256=row.get("output_sha256"),
        manifest_sha256=manifest_hash,
    )
    if any(
        not isinstance(result[key], str)
        or len(result[key]) != 64
        or any(char not in "0123456789abcdef" for char in result[key])
        for key in ("source_sha256", "output_sha256", "manifest_sha256")
    ):
        raise ValueError("Incomplete native QI surface provenance")
    return result


@lru_cache(maxsize=8)
def native_qi_surfaces(map_id):
    provenance = native_qi_surface_provenance(map_id)
    directory, _, _ = _publication()
    try:
        raw = protocol_catalog.read_bytes(directory / f"{map_id}.json")
    except OSError as error:
        raise ValueError("Published native QI map data is missing") from error
    if hashlib.sha256(raw).hexdigest() != provenance["output_sha256"]:
        raise ValueError("Published native QI map checksum mismatch")
    data = json.loads(raw)
    return NativeQISurfaces(
        data, map_id=map_id, source_sha256=provenance["source_sha256"]
    )
