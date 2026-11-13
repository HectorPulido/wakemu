import unittest
from types import SimpleNamespace
from unittest.mock import patch

from wakfu_server.achievements import rii_element_contract as contract


class ElementalEncounterTests(unittest.TestCase):
    def setUp(self):
        self.owner = SimpleNamespace(id=7)
        self.target = SimpleNamespace(
            id=-2,
            effect_stats={},
            effect_minima={28: 0, 29: 0, 30: 0, 31: 0},
            effect_maxima={28: 32767, 29: 32767, 30: 32767, 31: 32767},
        )
        self.fight = SimpleNamespace(
            current=self.owner,
            turn_id=1,
            actors={7: self.owner, -2: self.target},
            rii_element_lesson_contract={"owner": 7, "target": -2},
        )

    def test_four_valid_hits_can_occur_in_one_turn(self):
        self.assertTrue(contract.begin_turn(self.fight))
        for index, reference in enumerate((361189, 361189, 361189, 361192)):
            self.assertEqual(
                contract.hit(
                    self.fight,
                    source_id=7,
                    target_id=-2,
                    effect_reference=reference,
                    damage=1,
                ),
                25,
            )
            if index == 2:
                self.assertEqual(
                    self.target.effect_stats, {28: 32000, 29: 32000, 30: 32000, 31: 0}
                )
        self.assertEqual(self.fight.rii_element_lesson_contract["hits"], 4)

    def test_four_valid_hits_across_distinct_turns(self):
        for turn, reference in ((1, 361189), (3, 361190), (5, 361191), (7, 361192)):
            self.fight.turn_id = turn
            self.assertTrue(contract.begin_turn(self.fight))
            self.assertFalse(contract.begin_turn(self.fight))
            self.assertEqual(
                contract.hit(
                    self.fight,
                    source_id=7,
                    target_id=-2,
                    effect_reference=reference,
                    damage=1,
                ),
                25,
            )
        self.assertEqual(self.fight.rii_element_lesson_contract["hits"], 4)

    def test_wrong_element_actor_or_effect_never_damages_target(self):
        contract.begin_turn(self.fight)
        for changes in (
            {"source_id": 8},
            {"effect_reference": 361190},
            {"effect_reference": 1},
            {"damage": 0},
        ):
            event = {
                "source_id": 7,
                "target_id": -2,
                "effect_reference": 361189,
                "damage": 5,
            }
            event.update(changes)
            self.assertEqual(contract.hit(self.fight, **event), 0)
        self.assertEqual(self.fight.rii_element_lesson_contract.get("hits", 0), 0)

    def test_unrelated_target_untouched(self):
        self.assertIsNone(
            contract.hit(
                self.fight,
                source_id=7,
                target_id=-3,
                effect_reference=361189,
                damage=100,
            )
        )

    def test_rejected_preview_does_not_consume_a_hit_or_turn(self):
        from copy import deepcopy
        from wakfu_server.combat_entry_executor import private_entry_preview

        contract.begin_turn(self.fight)
        _, preview = private_entry_preview(
            self.fight, snapshot=lambda _: {}, clone=lambda value: deepcopy(value)
        )
        with self.assertRaises(ValueError):
            contract.hit(
                preview, source_id=7, target_id=-2, effect_reference=361189, damage=25
            )
            raise ValueError("A later native effect rejected the cast")
        self.assertEqual(self.fight.rii_element_lesson_contract.get("hits", 0), 0)
        self.assertEqual(self.fight.rii_element_lesson_contract.get("last_turn"), None)
        self.assertEqual(
            contract.hit(
                self.fight,
                source_id=7,
                target_id=-2,
                effect_reference=361189,
                damage=25,
            ),
            25,
        )

    def test_initialization_grants_once_and_uses_current_fight_actor(self):
        self.owner.team, self.target.team = 0, 1
        self.fight.phase = "active"
        self.fight.allocate_effect_uid = lambda: 123
        packets = []
        with patch(
            "wakfu_server.rii_lesson_grants.install", return_value=[10, 11, 12, 13]
        ) as install:
            self.assertTrue(contract.initialize(self.fight, packets, action_id=1))
            install.assert_called_once()
            self.assertEqual(
                self.fight.rii_element_lesson_contract["grant_uids"], [10, 11, 12, 13]
            )
            with self.assertRaises(ValueError):
                contract.initialize(self.fight, packets, action_id=1)


if __name__ == "__main__":
    unittest.main()
