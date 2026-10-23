"""Recover original scenario locations in bulk without activating gameplay."""
import csv
from pathlib import Path

from build_environmental_native_catalog import ROOT, REPORT, insert, load_sources

DOCUMENTS = (
    "monster-encyclopedia.json",
    "territory-protector-bonuses.json",
    "territory-map-cells.json",
)
SOURCE_KEY = "installed-environmental-source-v1"
MIGRATION = ROOT / "server/migrations/278_environmental_native_locations.sql"


def locations(environment, encyclopedia, bonuses, cells):
    """Join original protector identities, never names or coordinate guesses."""
    coverage = {
        (m["map_id"], r["region_id"])
        for m in cells["maps"]
        for r in m["regions"]
        if r["cells"]
    }
    rows, protectors, identities = [], {}, set()
    for territory in encyclopedia["territories"]:
        raw = territory["raw_native"]
        region, protector = territory["territory_id"], raw["ctC"]
        if region != raw["ctH"] or any(
            type(v) is not int or v <= 0 for v in (region, protector)
        ):
            raise ValueError("Invalid original protector territory")
        if (protector, region) in identities:
            raise ValueError("Duplicate original protector territory")
        identities.add((protector, region))
        definition = bonuses["territories"].get(str(region))
        map_id = None if definition is None else definition["map_id"]
        if map_id is not None and (type(map_id) is not int or map_id <= 0):
            raise ValueError("Invalid original territory map")
        if definition is not None and definition["territory_id"] != region:
            raise ValueError("Contradictory original territory map")
        protectors.setdefault(protector, set()).add((raw["ctD"], raw["ctF"]))
        rows.append((protector, region, map_id, (map_id, region) in coverage))
    for assignment in environment["protector_assignments"]:
        expected = tuple(assignment["challenge_group_ids"])
        if expected not in protectors.get(assignment["protector_id"], set()):
            raise ValueError(
                "Environmental assignment differs from original protector groups"
            )
    return sorted(rows)


DDL = """
-- Original location evidence only: no profile, schedule, spawn or reward activation.
CREATE TABLE environmental_native_location_sources (
 source_key text NOT NULL REFERENCES environmental_native_source_versions,
 catalog_revision text NOT NULL CHECK(length(catalog_revision)=64),
 document_path text NOT NULL, document_sha256 text NOT NULL CHECK(length(document_sha256)=64),
 PRIMARY KEY(source_key,document_path)
);
CREATE TABLE environmental_native_protector_territories (
 source_key text NOT NULL REFERENCES environmental_native_source_versions,
 protector_id integer NOT NULL CHECK(protector_id>0),
 region_id integer NOT NULL CHECK(region_id>0),
 map_id integer CHECK(map_id>0), native_cells_present boolean NOT NULL,
 CHECK(NOT native_cells_present OR map_id IS NOT NULL),
 PRIMARY KEY(source_key,protector_id,region_id)
);
"""
VIEW = """
CREATE VIEW environmental_native_scenario_locations AS
SELECT p.source_key,m.scenario_id,p.protector_id,p.ordinal AS protector_group_ordinal,
 p.group_id,m.ordinal AS scenario_group_ordinal,m.native_criteria,
 t.region_id,t.map_id,t.native_cells_present,false AS activation_qualified
FROM environmental_native_protector_groups p
JOIN environmental_native_group_members m USING(source_key,group_id)
LEFT JOIN environmental_native_protector_territories t USING(source_key,protector_id);
CREATE TRIGGER immutable_source BEFORE UPDATE OR DELETE ON environmental_native_location_sources
 FOR EACH ROW EXECUTE FUNCTION reject_environmental_native_source_mutation();
CREATE TRIGGER immutable_source BEFORE UPDATE OR DELETE ON environmental_native_protector_territories
 FOR EACH ROW EXECUTE FUNCTION reject_environmental_native_source_mutation();
"""


def build():
    from wakfu_server import native_catalog
    from wakfu_server.paths import DATA_ROOT

    environment, _, _ = load_sources()
    documents = [native_catalog.load(DATA_ROOT / name) for name in DOCUMENTS]
    rows = locations(environment, *documents)
    hashes, revision = native_catalog.document_hashes(), native_catalog.release()
    with MIGRATION.open("w") as stream:
        stream.write(DDL)
        insert(
            stream,
            "environmental_native_location_sources",
            ("source_key", "catalog_revision", "document_path", "document_sha256"),
            [(SOURCE_KEY, revision, name, hashes[name]) for name in DOCUMENTS],
        )
        insert(
            stream,
            "environmental_native_protector_territories",
            (
                "source_key",
                "protector_id",
                "region_id",
                "map_id",
                "native_cells_present",
            ),
            [(SOURCE_KEY, *row) for row in rows],
        )
        stream.write(VIEW)
    groups = {g["group_id"]: g["members"] for g in environment["groups"]}
    by_protector = {}
    for row in rows:
        by_protector.setdefault(row[0], []).append(row)
    path = REPORT / "environmental-original-scenario-locations.csv"
    with path.open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(
            (
                "scenario_id",
                "protector_id",
                "protector_group_ordinal",
                "group_id",
                "scenario_group_ordinal",
                "native_criteria",
                "region_id",
                "map_id",
                "native_cells_present",
            )
        )
        for assignment in environment["protector_assignments"]:
            for ordinal, group_id in enumerate(assignment["challenge_group_ids"]):
                for member_ordinal, member in enumerate(groups[group_id]):
                    for _, region, map_id, covered in by_protector[
                        assignment["protector_id"]
                    ]:
                        writer.writerow(
                            (
                                member["challenge_id"],
                                assignment["protector_id"],
                                ordinal,
                                group_id,
                                member_ordinal,
                                member["criteria"],
                                region,
                                map_id,
                                covered,
                            )
                        )
    return rows


if __name__ == "__main__":
    build()
