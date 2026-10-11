"""Offline native transport exclusions must be narrow and evidence driven."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from prepare_family_transport_dungeons import (
    classic_sources,
    optional_outside_component,
    native_spines,
)


class FamilyTransportPreparationTests(unittest.TestCase):
    def test_only_exact_neo_alternative_is_excluded_without_mutating_catalog(self):
        sources = [
            dict(
                id=1,
                map_id=9,
                destinations=[
                    dict(criterion=c)
                    for c in (
                        "IsNeoServer()",
                        "not IsNeoServer()",
                        "IsNeoServer() and HasState(2)",
                        "",
                    )
                ],
            )
        ]
        selected = classic_sources(sources, 9)
        self.assertEqual(len(selected[0]["destinations"]), 3)
        self.assertEqual(len(sources[0]["destinations"]), 4)

    def test_reachable_optional_internal_transport_cannot_be_erased(self):
        source = dict(
            id=1,
            map_id=9,
            x=7,
            y=7,
            z=0,
            approach_positions=[dict(x=0, y=0, z=0)],
            approach_blocks_center=True,
            destinations=[dict(map_id=9)],
        )
        with self.assertRaises(ValueError):
            optional_outside_component([source], [[0, 0, 0]])
        self.assertEqual(optional_outside_component([source], [[1, 0, 0]]), [1])

    def test_spines_do_not_repeat_regions_or_cross_paid_transport(self):
        links = [
            dict(
                source_region=a,
                destination_region=b,
                source_id=i,
                requires_item=paid,
                requires_kamas=False,
                instance_template=-1,
                criterion="",
                destination_position=[b, 0, 0],
            )
            for i, (a, b, paid) in enumerate(
                [(0, 1, False), (1, 0, False), (0, 2, True), (1, 3, False)]
            )
        ]
        paths = native_spines(
            dict(region_chain=[0], entry=[0, 0, 0], native_links=links)
        )
        self.assertEqual(paths[0]["region_chain"], [0, 1, 3])
        self.assertTrue(all(2 not in p["region_chain"] for p in paths))


class ProgressiveTransportArtifactsTests(unittest.TestCase):
    def test_multistage_candidates_increase_actual_spawn_threat_and_filter_roles(self):
        import json
        from extract_dungeon_family_bosses import load_role_catalog, role_allowed

        root = Path(__file__).resolve().parents[2]
        evidence = json.loads(
            (
                root
                / "docs/reports/dungeons/FAMILY-TRANSPORT-PROGRESSIVE-V2-20261010.json"
            ).read_text()
        )
        export = (
            root
            / ".runtime/local/duel-core-final-context-20261007-r7/r4-check/app/protocol/monsters.json"
        )
        if not export.is_file() or any(
            not (root / r["path"]).is_file()
            for r in evidence["records"]
            if r["status"] == "offline_configuration_prepared"
        ):
            self.skipTest(
                "Read-only native export and prepared local artifacts required"
            )
        catalog = load_role_catalog(export)
        prepared = [
            r
            for r in evidence["records"]
            if r["status"] == "offline_configuration_prepared"
        ]
        self.assertEqual(len(prepared), 9)
        self.assertEqual(sum(not r["collapsed_single_encounter"] for r in prepared), 4)
        for record in prepared:
            config = json.loads((root / record["path"]).read_text())
            self.assertEqual(config["version"], 5)
            plan = config["compiled_plan"]
            self.assertEqual(plan["progression_policy"], record["progression_policy"])
            threats = []
            for room in plan["rooms"]:
                final = room["order"] == len(plan["rooms"])
                for m in room["monsters"]:
                    self.assertTrue(
                        role_allowed(
                            catalog.get(m["ref_id"]),
                            final_room=final,
                            allowed_boss_references=record["boss_references"],
                        )
                    )
                threats.append(
                    sum(m["count"] * m["native_min_level"] for m in room["monsters"])
                )
            self.assertTrue(all(a < b for a, b in zip(threats, threats[1:])))
