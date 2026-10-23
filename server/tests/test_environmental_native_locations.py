"""Bulk original location joins preserve criteria and never activate content."""
import csv
import json
import unittest
from copy import deepcopy

from postgres_case import PostgresCase
from build_environmental_native_locations import ROOT, REPORT, locations


class EnvironmentalLocationValidationTests(unittest.TestCase):
    def test_unknown_maps_stay_unknown_and_original_group_conflicts_are_rejected(self):
        environment = dict(
            protector_assignments=[dict(protector_id=2, challenge_group_ids=[3, 4])]
        )
        encyclopedia = dict(
            territories=[
                dict(territory_id=5, raw_native=dict(ctH=5, ctC=2, ctD=3, ctF=4))
            ]
        )
        bonuses = dict(territories={})
        cells = dict(maps=[dict(map_id=6, regions=[dict(region_id=5, cells=[[0, 0]])])])
        self.assertEqual(
            locations(environment, encyclopedia, bonuses, cells), [(2, 5, None, False)]
        )
        bonuses["territories"]["5"] = dict(territory_id=5, map_id=6)
        self.assertEqual(
            locations(environment, encyclopedia, bonuses, cells), [(2, 5, 6, True)]
        )
        wrong = deepcopy(environment)
        wrong["protector_assignments"][0]["challenge_group_ids"].reverse()
        with self.assertRaisesRegex(ValueError, "original protector groups"):
            locations(wrong, encyclopedia, bonuses, cells)
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            locations(
                environment,
                dict(territories=encyclopedia["territories"] * 2),
                bonuses,
                cells,
            )


class EnvironmentalNativeLocationTests(PostgresCase):
    def test_complete_original_location_join_preserves_every_criteria_and_disabled_boundary(
        self,
    ):
        from wakfu_server import native_catalog
        from wakfu_server.paths import DATA_ROOT

        original = json.loads(
            (
                ROOT
                / "agents_docs/reports/recurring-missions/ENVIRONMENTAL-SCENARIOS-INVENTORY-20261011.json"
            ).read_text()
        )
        encyclopedia = native_catalog.load(DATA_ROOT / "monster-encyclopedia.json")
        bonuses = native_catalog.load(DATA_ROOT / "territory-protector-bonuses.json")[
            "territories"
        ]
        cells = native_catalog.load(DATA_ROOT / "territory-map-cells.json")
        coverage = {
            (m["map_id"], r["region_id"])
            for m in cells["maps"]
            for r in m["regions"]
            if r["cells"]
        }
        groups = {g["group_id"]: g["members"] for g in original["groups"]}
        assignments = {
            a["protector_id"]: a["challenge_group_ids"]
            for a in original["protector_assignments"]
        }
        expected = []
        for territory in encyclopedia["territories"]:
            raw = territory["raw_native"]
            if raw["ctC"] not in assignments:
                continue
            self.assertEqual(assignments[raw["ctC"]], [raw["ctD"], raw["ctF"]])
            region = raw["ctH"]
            definition = bonuses.get(str(region))
            map_id = None if definition is None else definition["map_id"]
            for ordinal, group in enumerate((raw["ctD"], raw["ctF"])):
                for member_ordinal, member in enumerate(groups[group]):
                    expected.append(
                        (
                            member["challenge_id"],
                            raw["ctC"],
                            ordinal,
                            group,
                            member_ordinal,
                            member["criteria"],
                            region,
                            map_id,
                            (map_id, region) in coverage,
                            False,
                        )
                    )
        with self.store.connection() as db:
            actual = db.execute(
                "SELECT scenario_id,protector_id,protector_group_ordinal,group_id,"
                "scenario_group_ordinal,native_criteria,region_id,map_id,native_cells_present,"
                "activation_qualified FROM environmental_native_scenario_locations"
            ).fetchall()
            self.assertEqual(
                sorted(tuple(r.values()) for r in actual), sorted(expected)
            )
            self.assertEqual(len(actual), 1549)
            self.assertEqual(len({r["scenario_id"] for r in actual}), 1191)
            self.assertEqual(sum(r["native_cells_present"] for r in actual), 1498)
            self.assertEqual(len({r["map_id"] for r in actual}), 55)
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_native_protector_territories"
                ).fetchone()["n"],
                105,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_runtime_profiles"
                ).fetchone()["n"],
                0,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_reward_entitlements"
                ).fetchone()["n"],
                0,
            )
            missing = db.execute(
                "SELECT scenario_id FROM environmental_native_scenarios s WHERE NOT EXISTS "
                "(SELECT 1 FROM environmental_native_scenario_locations l "
                "WHERE l.source_key=s.source_key AND l.scenario_id=s.scenario_id)"
            ).fetchall()
            self.assertEqual(len(missing), 17)
            sources = db.execute(
                "SELECT * FROM environmental_native_location_sources"
            ).fetchall()
            hashes = native_catalog.document_hashes()
            self.assertEqual(len(sources), 3)
            self.assertTrue(
                all(
                    r["catalog_revision"] == native_catalog.release()
                    and r["document_sha256"] == hashes[r["document_path"]]
                    for r in sources
                )
            )
            with self.assertRaisesRegex(Exception, "append-only"), db.transaction():
                db.execute("DELETE FROM environmental_native_protector_territories")
        with (
            REPORT / "environmental-original-scenario-locations.csv"
        ).open() as stream:
            exported = list(csv.DictReader(stream))
        self.assertEqual(
            sorted(
                (
                    int(r["scenario_id"]),
                    int(r["protector_id"]),
                    int(r["protector_group_ordinal"]),
                    int(r["group_id"]),
                    int(r["scenario_group_ordinal"]),
                    r["native_criteria"],
                    int(r["region_id"]),
                    int(r["map_id"]) if r["map_id"] else None,
                    r["native_cells_present"] == "True",
                    False,
                )
                for r in exported
            ),
            sorted(expected),
        )
