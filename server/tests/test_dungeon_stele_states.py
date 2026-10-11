"""Owned boss carrier and immutable native state closure boundaries."""
from copy import deepcopy
from types import SimpleNamespace
import unittest
from wakfu_server import dungeon_stele_states


class DungeonSteleStateTests(unittest.TestCase):
    def setUp(self):
        self.fight = SimpleNamespace(
            id=17,
            phase="active",
            actors={
                -3: SimpleNamespace(team=1),
                -4: SimpleNamespace(team=1),
                9: SimpleNamespace(team=0),
            },
        )
        self.monsters = {-3: {"ref": 100}, -4: {"ref": 101}}
        self.snapshot = dict(
            fight_id=17, player_team=0, selections=[dict(state_ids=[4020])]
        )
        self.rooms = [
            dict(
                monsters=[
                    dict(ref_id=100, role="boss"),
                    dict(ref_id=101, role="ordinary"),
                ]
            )
        ]
        self.catalog = dict(
            states={"4020": dict(maximum_level=1, effect_ids=[10])},
            effects={
                "10": dict(children=[11], effect_class=330),
                "11": dict(children=[], effect_class=57),
            },
        )

    def test_only_roster_boss_receives_the_selected_native_state(self):
        receipt = dungeon_stele_states.plan(
            self.fight, self.monsters, self.snapshot, self.rooms, self.catalog
        )
        self.assertEqual(receipt["actor_ids"], [-3])
        self.assertEqual(receipt["state_ids"], [4020])
        changed = deepcopy(self.catalog)
        changed["effects"]["11"]["effect_class"] = 55
        self.assertNotEqual(
            receipt["native_sha256"],
            dungeon_stele_states.plan(
                self.fight, self.monsters, self.snapshot, self.rooms, changed
            )["native_sha256"],
        )

    def test_ambiguous_missing_or_player_carriers_reject(self):
        for monsters in (
            {-4: {"ref": 101}},
            {-3: {"ref": 100}, -4: {"ref": 100}},
            {9: {"ref": 100}},
        ):
            with self.assertRaises(ValueError):
                dungeon_stele_states.plan(
                    self.fight, monsters, self.snapshot, self.rooms, self.catalog
                )

    def test_unknown_or_incomplete_native_closure_rejects(self):
        for catalog in (
            dict(states={}, effects={}),
            dict(
                states=self.catalog["states"],
                effects={"10": self.catalog["effects"]["10"]},
            ),
        ):
            with self.assertRaises(ValueError):
                dungeon_stele_states.plan(
                    self.fight, self.monsters, self.snapshot, self.rooms, catalog
                )

    def test_foreign_or_published_encounter_rejects(self):
        self.snapshot["fight_id"] = 18
        with self.assertRaises(ValueError):
            dungeon_stele_states.plan(
                self.fight, self.monsters, self.snapshot, self.rooms, self.catalog
            )
        self.snapshot["fight_id"] = 17
        self.fight.phase = "finished"
        with self.assertRaises(ValueError):
            dungeon_stele_states.plan(
                self.fight, self.monsters, self.snapshot, self.rooms, self.catalog
            )


if __name__ == "__main__":
    unittest.main()
