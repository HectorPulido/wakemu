"""Initialization adoption retains PA listeners on the published Fight."""
from copy import deepcopy
import gc
import unittest
from unittest.mock import patch
from weakref import ref

from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_actor_snapshot import _adopt_initialized_fight
from wakfu_server.combat_characteristic_link import (
    bind_characteristic_stats,
    characteristic_adoption_bindings,
)


class InitializedCharacteristicAdoptionTests(unittest.TestCase):
    def fixture(self):
        actors = [
            Actor(7, 0, (0, 0, 0), 100, 6, 3, 10, 1),
            Actor(-1, 1, (1, 0, 0), 100, 6, 3, 9, 1),
        ]
        fight = Fight(
            81, actors, {(0, 0, 0), (1, 0, 0)}, {0: {(0, 0, 0)}, 1: {(1, 0, 0)}}
        )
        for actor in fight.actors.values():
            actor.effect_stats = {7: 10}
        bind_characteristic_stats(fight)
        return fight

    def test_adopted_listener_callback_targets_actual_fight_and_keeps_actor_alias(self):
        fight = self.fixture()
        actor = fight.actors[7]
        preview = deepcopy(fight)
        preview.native_characteristic_links = {91: {"source_id": 7, "source_stat": 7}}
        _adopt_initialized_fight(fight, preview, None)
        observed = []
        with patch(
            "wakfu_server.combat_characteristic_link._refresh",
            side_effect=lambda current, row: observed.append(current),
        ):
            actor.effect_stats[7] = 20
        self.assertEqual(len(observed), 1)
        self.assertIs(observed[0], fight)
        self.assertIs(fight.actors[7], actor)
        self.assertIs(actor.effect_stats._fight, fight)
        self.assertEqual(len(characteristic_adoption_bindings(fight)), 2)

    def test_completed_adoption_does_not_retain_preview_through_stat_listener(self):
        fight = self.fixture()
        preview = deepcopy(fight)
        old = ref(preview)
        _adopt_initialized_fight(fight, preview, None)
        del preview
        gc.collect()
        self.assertIsNone(old())
        self.assertIs(fight.actors[7].effect_stats._fight, fight)


if __name__ == "__main__":
    unittest.main()
