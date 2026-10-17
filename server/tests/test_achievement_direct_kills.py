"""Exact original-breed kill predicates do not invent native counters."""
import unittest
from wakfu_server.achievements import engine, catalog


def state():
    return dict(
        variables={},
        objectives=[],
        running=[],
        completed=[],
        tracking=[],
        recent=[],
        completion_dates={},
    )


class AchievementDirectKillTests(unittest.TestCase):
    def test_installed_catalog_preserves_variable_breed_provenance(self):
        rules = catalog.load()
        self.assertEqual(len(rules["definitions"]), 30)
        self.assertEqual(
            sum(len(r["objectives"]) for r in rules["definitions"].values()), 69
        )
        objective = rules["definitions"][238]["objectives"][0]
        self.assertEqual(
            rules["breed_variables"][objective["breed_id"]], objective["variable_id"]
        )

    def test_exact_breed_objectives_accumulate_across_fights_and_grant_once(self):
        rules = dict(
            breed_variables={},
            definitions={
                2980: dict(
                    objectives=[
                        dict(objective_id=6222, breed_id=4086, required_kills=1),
                        dict(objective_id=6223, breed_id=4101, required_kills=1),
                    ],
                    prerequisites=[],
                    rewards=[dict(aeV=5, ckl=[12686, 20])],
                )
            },
        )
        first, grants, added, completed = engine.advance(
            state(), dict(original_breeds=[4086, 4086, 5891]), rules, now_ms=10
        )
        self.assertEqual(added, [6222])
        self.assertEqual((grants, completed, first["variables"]), ([], [], {}))
        second, grants, added, completed = engine.advance(
            first, dict(original_breeds=[4101]), rules, now_ms=20
        )
        self.assertEqual((added, completed), ([6223], [2980]))
        self.assertEqual(len(grants), 1)
        self.assertEqual(second["completion_dates"], {"2980": 20})
        _, grants, added, completed = engine.advance(
            second, dict(original_breeds=[4086, 4101]), rules, now_ms=30
        )
        self.assertEqual((grants, added, completed), ([], [], []))

    def test_direct_kill_coexists_with_variable_and_dungeon_predicates(self):
        rules = dict(
            breed_variables={4086: 51},
            definitions={
                1: dict(
                    objectives=[
                        dict(objective_id=11, breed_id=4086, required_kills=1),
                        dict(
                            objective_id=12, variable_id=51, operator="==", threshold=1
                        ),
                        dict(objective_id=13, dungeon_id=90),
                    ],
                    prerequisites=[],
                    rewards=[],
                )
            },
        )
        after, _, added, completed = engine.advance(
            state(),
            dict(original_breeds=[4086], completed_dungeon_id=90),
            rules,
            now_ms=1,
        )
        self.assertEqual(added, [11, 12, 13])
        self.assertEqual(completed, [1])
        self.assertEqual(after["variables"], {"51": 1})

    def test_wrong_species_and_dungeon_cannot_satisfy_direct_kill(self):
        rules = dict(
            breed_variables={},
            definitions={
                5164: dict(
                    objectives=[
                        dict(objective_id=10631, breed_id=5526, required_kills=1),
                        dict(objective_id=10632, breed_id=5527, required_kills=1),
                    ],
                    prerequisites=[],
                    rewards=[],
                )
            },
        )
        after, grants, added, completed = engine.advance(
            state(),
            dict(original_breeds=[5891, 4674], completed_dungeon_id=5526),
            rules,
            now_ms=1,
        )
        self.assertEqual((grants, added, completed), ([], [], []))
        self.assertEqual(after["objectives"], [])
