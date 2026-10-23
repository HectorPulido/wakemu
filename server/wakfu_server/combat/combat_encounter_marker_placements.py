"""Immutable database placements for original neutral encounter markers."""
from dataclasses import dataclass
from functools import lru_cache
import hashlib
import json
from types import MappingProxyType


@dataclass(frozen=True)
class EncounterMarkerPlacements:
    policy: str
    authority: str
    source_url: str
    coordinate_authority: str
    map_id: int
    monster_references: tuple
    catalog_revision: str
    placements: tuple

    def declarations(self):
        return [
            dict(
                reference=row["area_reference"],
                level=row["level"],
                cell=[row["x"], row["y"], row["z"]],
            )
            for row in self.placements
        ]


def _database():
    from wakfu_server import native_catalog

    return native_catalog._database()


def _scope(map_id, references):
    references = tuple(sorted(references))
    if (
        type(map_id) is not int
        or not references
        or any(type(value) is not int or value <= 0 for value in references)
    ):
        raise ValueError("Invalid encounter marker placement scope")
    return references


@lru_cache(maxsize=64)
def _version(policy):
    with _database().connection() as db:
        version = db.execute(
            "SELECT * FROM encounter_marker_placement_versions WHERE policy=%s",
            (policy,),
        ).fetchone()
        rows = db.execute(
            "SELECT ordinal,area_reference,level,x,y,z FROM encounter_marker_placements "
            "WHERE policy=%s ORDER BY ordinal",
            (policy,),
        ).fetchall()
    if version is None:
        raise ValueError("Unknown immutable encounter marker placement policy")
    placements = tuple(dict(row) for row in rows)
    checksum = hashlib.sha256(
        json.dumps(
            placements,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
    ).hexdigest()
    references = _scope(version["map_id"], version["monster_references"])
    if (
        version["policy"] != policy
        or not policy.startswith("wakemu.")
        or not version["authority"]
        or not version["source_url"]
        or not version["coordinate_authority"]
        or tuple(version["monster_references"]) != references
        or len(placements) != version["expected_count"]
        or checksum != version["placements_sha256"]
        or tuple(row["ordinal"] for row in placements) != tuple(range(len(placements)))
        or len({(row["x"], row["y"]) for row in placements}) != len(placements)
    ):
        raise ValueError("Immutable encounter marker placement data changed")
    return EncounterMarkerPlacements(
        policy,
        version["authority"],
        version["source_url"],
        version["coordinate_authority"],
        version["map_id"],
        references,
        version["catalog_revision"],
        tuple(MappingProxyType(row) for row in placements),
    )


def active_marker_placements(map_id, monster_references):
    """Read the active pointer once for a new, unpublished scene admission."""
    from wakfu_server import native_catalog

    references = _scope(map_id, monster_references)
    with _database().connection() as db:
        selected = db.execute(
            "SELECT policy FROM encounter_marker_placement_active "
            "WHERE map_id=%s AND monster_references=%s::integer[]",
            (map_id, list(references)),
        ).fetchone()
    if selected is None:
        raise ValueError("Encounter has no published native marker placements")
    result = _version(selected["policy"])
    if (result.map_id, result.monster_references) != (
        map_id,
        references,
    ) or result.catalog_revision != native_catalog.release():
        raise ValueError("Encounter marker placements differ from scope or catalog")
    return result
