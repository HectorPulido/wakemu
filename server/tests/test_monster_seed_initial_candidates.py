"""Seed compatibility and mixed-row isolation for native monster growth."""
from contextlib import contextmanager
import unittest
from unittest.mock import patch

from wakfu_server import (
    ecology_plants,
    monster_collect,
    monster_family_stages,
    monsters,
    planting,
)
from wakfu_server.planting_runtime import NoEligibleMonsterGrowth, monster_growth_member


class MonsterSeedInitialCandidateTests(unittest.TestCase):
    def test_tutorial_family_seed_186_produces_a_viable_family_113_member(self):
        definition = planting.RESOURCES[186]
        self.assertTrue(definition["monster_resource"])
        self.assertIn(113, definition["monster_family_ids"])
        rows = monster_family_stages.initial_candidates(113)
        self.assertEqual({row["reference"] for row in rows}, {135, 95, 1275, 4544})
        self.assertTrue(all(38 <= row["min_level"] <= 40 for row in rows))
        self.assertNotIn(138, {row["reference"] for row in rows})
        self.assertNotIn(94, {row["reference"] for row in rows})
        member = monster_growth_member(
            dict(map_id=1, instance_id=0, x=0, y=0, z=0),
            definition,
            decision_seed="family-113-resource-186-qualification",
        )
        self.assertIn(member["ref"], {row["reference"] for row in rows})
        self.assertIn(
            monsters.REFERENCES[member["ref"]]["family_id"],
            definition["monster_family_ids"],
        )

    def test_band_selection_handles_invalid_candidates_eligibility_and_fallback(self):
        stages = monster_family_stages

        def row(reference, level):
            return {
                "reference": reference,
                "min_level": level,
                "boss_classification": "regular",
                "world_properties": [],
            }

        families = {
            9001: {
                "family_id": 9001,
                "resource_references": [901],
                "tiers": [
                    {"rank": 0, "candidates": [row(1, 1)]},
                    {"rank": 1, "candidates": [row(2, 10)]},
                    {"rank": 2, "candidates": [row(3, 20)]},
                ],
            },
            9002: {
                "family_id": 9002,
                "resource_references": [902],
                "tiers": [
                    {"rank": 0, "candidates": [row(4, 1)]},
                    {"rank": 1, "candidates": [row(5, 10)]},
                ],
            },
        }
        fake_references = {
            reference: {"name": f"monster {reference}"} for reference in range(1, 6)
        }
        fake_actions = {(2, 1): {"csP": 9101, "clT": ""}}
        fake_seeds = {9101: {"item_reference": 9101, "resource_reference": 901}}
        stages._initial_references.cache_clear()
        self.addCleanup(stages._initial_references.cache_clear)
        with patch.dict(stages.FAMILIES, families, clear=True), patch.object(
            monsters, "REFERENCES", fake_references
        ), patch.object(
            monster_collect, "_actions", return_value=fake_actions
        ), patch.object(
            planting, "SEEDS", fake_seeds
        ), patch.object(
            stages,
            "publication_viable",
            side_effect=lambda ref, _level: ref != 1 and ref != 4,
        ):
            stages._initial_references.cache_clear()
            self.assertEqual(
                [
                    candidate["reference"]
                    for candidate in stages.initial_candidates(9001)
                ],
                [2],
            )
            self.assertEqual(
                [
                    candidate["reference"]
                    for candidate in stages.initial_candidates(
                        9001, eligible_references={3}
                    )
                ],
                [3],
            )
            self.assertEqual(
                [
                    candidate["reference"]
                    for candidate in stages.initial_candidates(9002)
                ],
                [5],
            )
        stages._initial_references.cache_clear()

    def test_every_native_monster_seed_resource_has_a_producible_candidate(self):
        seed_rows = [
            seed
            for seed in planting.SEEDS.values()
            if planting.RESOURCES[seed["resource_reference"]]["monster_resource"]
        ]
        self.assertTrue(seed_rows, "native monster seed catalog is empty")
        unavailable_families = set()
        for seed in seed_rows:
            with self.subTest(seed=seed["item_reference"]):
                definition = planting.RESOURCES[seed["resource_reference"]]
                native_family_refs = {
                    reference
                    for reference, monster in monsters.REFERENCES.items()
                    if monster["family_id"] in definition["monster_family_ids"]
                }
                try:
                    member = monster_growth_member(
                        dict(map_id=1, instance_id=0, x=0, y=0, z=0),
                        definition,
                        decision_seed=f"seed-census:{seed['item_reference']}",
                    )
                except NoEligibleMonsterGrowth:
                    self.assertFalse(
                        native_family_refs,
                        "Family has native templates but no seed can produce one",
                    )
                    for family in definition["monster_family_ids"]:
                        catalog_family = monster_family_stages.FAMILIES.get(family)
                        self.assertTrue(
                            catalog_family is None
                            or catalog_family.get("missing_catalog")
                            or not catalog_family.get("tiers"),
                            f"Family {family} is unavailable without a missing catalog",
                        )
                        unavailable_families.add(family)
                    continue
                self.assertIn(
                    monsters.REFERENCES[member["ref"]]["family_id"],
                    definition["monster_family_ids"],
                )
                self.assertGreater(member["ref"], 0)
        self.assertEqual(unavailable_families, {469, 470})

    def test_invalid_birth_row_does_not_block_later_valid_row(self):
        resource_reference = next(
            seed["resource_reference"]
            for seed in planting.SEEDS.values()
            if planting.RESOURCES[seed["resource_reference"]]["monster_resource"]
        )
        rows = [
            dict(
                resource_uid=uid,
                map_id=1,
                instance_id=0,
                x=uid,
                y=0,
                z=0,
                resource_reference=resource_reference,
                stage=1,
                creation_time=0,
            )
            for uid in (101, 102)
        ]
        original_rows = [dict(row) for row in rows]

        class Cursor:
            def execute(self, *_args):
                return self

            def fetchall(self):
                return rows

        class Store:
            @contextmanager
            def connection(self):
                yield Cursor()

        snapshot = {"world_epoch": "seed-row-isolation", "now_ms": 100000}
        ecology_plants._CURSORS.pop(snapshot["world_epoch"], None)
        self.addCleanup(ecology_plants._CURSORS.pop, snapshot["world_epoch"], None)
        good_member = {"ref": 777, "family_id": 113}

        def build(resource, definition, **kwargs):
            if resource["resource_uid"] == 101:
                raise NoEligibleMonsterGrowth("test invalid family")
            return good_member

        with patch.object(
            ecology_plants, "monster_growth_member", side_effect=build
        ), patch.object(ecology_plants, "_seed_log"):
            plans = ecology_plants._prepare_birth_batch(
                Store(), snapshot, [resource_reference], 30, set()
            )

        self.assertEqual(len(plans), 1)
        self.assertEqual(
            [row["expected"]["resource_uid"] for row in plans[0]["resources"]],
            [102],
        )
        self.assertEqual(plans[0]["resources"][0]["member"], good_member)
        self.assertEqual(
            ecology_plants._CURSORS[snapshot["world_epoch"]]["monster_bulk"], 102
        )
        self.assertEqual(rows, original_rows)

    def test_unrelated_value_error_is_not_treated_as_an_unavailable_family(self):
        resource = dict(resource_uid=103, map_id=1, instance_id=0, x=0, y=0, z=0)
        definition = {"resource_reference": 1}
        with patch.object(
            ecology_plants,
            "monster_growth_member",
            side_effect=ValueError("unrelated malformed state"),
        ), patch.object(ecology_plants, "_seed_log"):
            with self.assertRaisesRegex(ValueError, "unrelated malformed state"):
                ecology_plants._growth_member(resource, definition)


if __name__ == "__main__":
    unittest.main()
