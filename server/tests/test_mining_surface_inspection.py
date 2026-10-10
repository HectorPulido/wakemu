"""The inspection tool must not turn suitability into invented spawn identity."""
import importlib.util
from pathlib import Path
import unittest

path = (
    Path(__file__).resolve().parents[2]
    / "client-tools/inspection/export-mining-surfaces.py"
)
spec = importlib.util.spec_from_file_location("mining_inspection", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class MiningInspectionTests(unittest.TestCase):
    def test_explicit_zero_overrides_positive_family_and_other_professions_excluded(
        self,
    ):
        resources = [
            dict(
                resource_reference=37,
                family_id=7,
                stage_definitions=[dict(actions=[dict(profession_id=73)])],
            ),
            dict(
                resource_reference=23,
                family_id=7,
                stage_definitions=[dict(actions=[dict(profession_id=64)])],
            ),
        ]
        grounds = [
            dict(ground_id=1, resources={"37": 0}, families={"7": 100}),
            dict(ground_id=2, resources={}, families={"7": 50}),
        ]
        self.assertEqual(module.eligibility(resources, grounds), {"2": [37]})


planner_path = path.parent / "plan-mining-veins.py"
planner_spec = importlib.util.spec_from_file_location("mining_planner", planner_path)
planner = importlib.util.module_from_spec(planner_spec)
planner_spec.loader.exec_module(planner)


class MiningPlannerTests(unittest.TestCase):
    def test_full_coverage_allocates_every_accessible_slot_and_all_species(self):
        from copy import deepcopy

        catalog, evidence, policy = self.fixture()
        fallback_species = deepcopy(catalog[0])
        fallback_species["resource_reference"] = 643
        fallback_species["stage_definitions"][0]["actions"][0]["item_reference"] = 0
        fallback_species["stage_definitions"][0]["actions"][0]["product_references"] = [
            1846
        ]
        catalog.append(fallback_species)
        policy.update(
            max_per_map=0,
            minimum_spacing=0,
            coverage_mode="all_accessible",
            minimum_per_species=1,
            allow_species_ground_fallback=True,
        )
        index = {
            (r["x"], r["y"], r["z"]): dict(
                ground_id=161, eligible_refs={37}, approaches={(r["x"], -1, 3)}
            )
            for r in evidence["candidate_surfaces"]
        }
        index[(9, 0, 3)]["approaches"] = set()

        def run():
            return planner.plan(
                catalog,
                evidence,
                surface=None,
                geometry=None,
                navigation=lambda _: index,
                supports_action=lambda _: True,
                policy=policy,
                source_sha256="d" * 64,
            )

        result = run()
        self.assertEqual(result, run())
        self.assertEqual(9, len(result["placements"]))
        self.assertEqual([37, 643], result["selected_species"])
        self.assertEqual(9, sum(result["species_counts"].values()))
        self.assertEqual(1, result["exclusions"]["no_native_resource_approach"])
        fallback = [p for p in result["placements"] if p["resource_reference"] == 643]
        self.assertEqual(1, len(fallback))
        self.assertEqual(
            "local-mineral-ground-fallback",
            fallback[0]["provenance"]["species_ground_policy"],
        )
        self.assertFalse(result["official_distribution"])

    def fixture(self):
        catalog = [
            dict(
                resource_reference=37,
                family_id=7,
                stage_definitions=[
                    dict(
                        stage_id=1,
                        actions=[
                            dict(
                                profession_id=73,
                                item_reference=1846,
                                criteria="",
                                minimum_level=0,
                                action_id=1632,
                                raw_getters={"cvF": 0},
                            )
                        ],
                    )
                ],
            )
        ]
        rows = [
            dict(
                map_id=527,
                x=x,
                y=0,
                z=3,
                ground_id=161,
                eligible_resource_references=[37],
                chunk="0_0",
                environment_chunk_sha256="a" * 64,
            )
            for x in range(10)
        ]
        evidence = dict(
            candidate_surfaces=rows,
            assets=[
                dict(map_id=527, environment_sha256="b" * 64, topology_sha256="c" * 64)
            ],
            errors=[],
        )
        policy = dict(
            seed=20261010,
            density_basis_points=10000,
            max_per_map=8,
            minimum_spacing=4,
            level_scale=20,
            level_power=2,
            precious_weight_basis_points=200,
        )
        return catalog, evidence, policy

    def test_deterministic_exact_fields_spacing_and_no_apply(self):
        catalog, evidence, policy = self.fixture()

        def run():
            return planner.plan(
                catalog,
                evidence,
                surface=lambda *args: {"ground_id": 161},
                geometry=lambda mid: {
                    "edges": [
                        ((r["x"], -1, 3), (r["x"], 0, 3))
                        for r in evidence["candidate_surfaces"]
                    ]
                },
                suitable=lambda *args: 1,
                source_sha256="d" * 64,
                policy=policy,
            )

        first = run()
        self.assertEqual(first, run())
        self.assertFalse(first["applied"])
        rows = first["placements"]
        self.assertEqual([r["x"] for r in rows], [0, 4, 8])
        for row in rows:
            self.assertEqual(
                set(row),
                {
                    "resource_uid",
                    "map_id",
                    "instance_id",
                    "x",
                    "y",
                    "z",
                    "resource_reference",
                    "stage",
                    "respawn_seconds",
                    "provenance",
                },
            )
            self.assertTrue(0 < row["resource_uid"] < 2**63)
            self.assertFalse(row["provenance"]["official_spawn"])

    def test_unknown_geometry_and_conflicting_heights_are_excluded(self):
        catalog, evidence, policy = self.fixture()
        evidence["candidate_surfaces"].append(
            dict(evidence["candidate_surfaces"][0], z=4)
        )

        def unknown(_):
            raise ValueError("Unavailable native map")

        result = planner.plan(
            catalog,
            evidence,
            surface=lambda *args: {},
            geometry=unknown,
            source_sha256="d" * 64,
            policy=policy,
        )
        self.assertEqual(result["placements"], [])
        self.assertEqual(result["exclusions"]["ambiguous_height_at_same_xy"], 2)
        self.assertEqual(result["exclusions"]["unknown_server_geometry"], 9)

    def test_invalid_distribution_policy_fails_before_geometry(self):
        catalog, evidence, policy = self.fixture()
        policy["density_basis_points"] = 10001
        with self.assertRaises(ValueError):
            planner.plan(
                catalog,
                evidence,
                surface=None,
                geometry=None,
                source_sha256="d" * 64,
                policy=policy,
            )

    def test_single_eligible_high_level_is_rarer_and_alternate_variants_are_sparse(
        self,
    ):
        from copy import deepcopy

        catalog, evidence, policy = self.fixture()
        policy.update(max_per_map=1000, minimum_spacing=0)
        evidence["candidate_surfaces"] = [
            dict(evidence["candidate_surfaces"][0], x=x) for x in range(500)
        ]
        catalog[0]["stage_definitions"].append(
            dict(
                stage_id=2,
                actions=[
                    dict(
                        catalog[0]["stage_definitions"][0]["actions"][0],
                        action_id=70,
                        item_reference=11478,
                    )
                ],
            )
        )

        def run(definitions):
            return planner.plan(
                definitions,
                evidence,
                surface=lambda *args: {"ground_id": 161},
                geometry=lambda _: {
                    "edges": [((x, -1, 3), (x, 0, 3)) for x in range(500)]
                },
                suitable=lambda *args: 1,
                source_sha256="d" * 64,
                policy=policy,
            )

        low = run(catalog)
        high_catalog = deepcopy(catalog)
        for stage in high_catalog[0]["stage_definitions"]:
            stage["actions"][0]["minimum_level"] = 100
        high = run(high_catalog)
        self.assertEqual(len(low["placements"]), 500)
        self.assertLess(len(high["placements"]), 50)
        self.assertGreater(len(high["placements"]), 0)
        alternates = sum(
            p["provenance"]["selected_alternate"] for p in low["placements"]
        )
        self.assertGreater(alternates, 0)
        self.assertLess(alternates, 50)
