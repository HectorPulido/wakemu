"""Rift population scans preserve lifecycle while bounding map validation."""
import unittest
from unittest.mock import patch

from wakfu_server.combat_global_pv_collections import (
    initialize_global_pv_collections,
    set_global_fighter_status,
    unregister_global_fighter,
)
from wakfu_server.combat_global_pv_read_view import in_play_actors
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_trove_long_map import NativeTroveLongMap


class RiftPopulationReadViewTests(unittest.TestCase):
    def fixture(self, count=4):
        actors = [
            Actor(index + 1, index % 2, (index, 0, 0), 100, 6, 6, 10, 10)
            for index in range(count)
        ]
        fight = Fight(
            99,
            actors,
            {actor.position for actor in actors},
            {team: {a.position for a in actors if a.team == team} for team in (0, 1)},
        )
        initialize_global_pv_collections(fight, tuple(fight.actors))
        return fight

    def test_population_uses_lifecycle_and_refreshes_after_mutation(self):
        fight = self.fixture()
        set_global_fighter_status(fight, 2, "OFF_PLAY")
        set_global_fighter_status(fight, 3, "OUT_OF_PLAY")
        unregister_global_fighter(fight, 4)
        before = in_play_actors(fight)
        self.assertEqual([a.id for a in before], [1])
        set_global_fighter_status(fight, 2, "IN_PLAY")
        self.assertEqual([a.id for a in in_play_actors(fight)], [1, 2])
        self.assertEqual([a.id for a in before], [1])
        self.assertEqual(set(fight.actors), {1, 2, 3, 4})

    def test_history_size_does_not_multiply_native_map_validation(self):
        original = NativeTroveLongMap.__init__
        for quantity in (4, 120):
            fight = self.fixture(quantity)
            calls = []

            def counted(instance, *args, **kwargs):
                calls.append(1)
                original(instance, *args, **kwargs)

            with patch.object(NativeTroveLongMap, "__init__", counted):
                self.assertEqual(len(in_play_actors(fight)), quantity)
            self.assertEqual(len(calls), 1)

    def test_death_reconciliation_validates_population_once_and_preserves_turn(self):
        from wakfu_server.combat_death_reconciliation import (
            prepare_death_reconciliation,
        )

        original = NativeTroveLongMap.__init__
        for quantity in (4, 120):
            fight = self.fixture(quantity)
            for identity in range(3, quantity + 1):
                set_global_fighter_status(fight, identity, "OUT_OF_PLAY")
            # The plan consumes native membership, not an HP heuristic.
            fight.actors[2].hp = 0
            fight.order = [1, 2]
            fight.turn_index = 1
            calls = []

            def counted(instance, *args, **kwargs):
                calls.append(1)
                original(instance, *args, **kwargs)

            with patch.object(NativeTroveLongMap, "__init__", counted):
                plan = prepare_death_reconciliation(fight)
            self.assertEqual(len(calls), 1)
            self.assertEqual(plan.current_id, 2)
            self.assertEqual(plan.current_index, 1)
            self.assertEqual(plan.surviving_order, (1, 2))
            self.assertEqual(plan.alive_teams, frozenset((0, 1)))
            self.assertEqual(len(fight.actors), quantity)

    def test_invalid_authority_is_rejected_but_custom_hooks_are_preserved(self):
        fight = self.fixture()
        fight.native_global_pv_collections["fighter_status"]["1"] = "invalid"
        with self.assertRaisesRegex(ValueError, "native fighter status"):
            in_play_actors(fight)
        calls = []
        fight._in_play = lambda actor: calls.append(actor.id) or actor.id == 3
        self.assertEqual([a.id for a in in_play_actors(fight)], [3])
        self.assertEqual(calls, [1, 2, 3, 4])

        class CustomFight(Fight):
            def _in_play(self, actor):
                return actor.id == 2

        custom = object.__new__(CustomFight)
        custom.__dict__.update(fight.__dict__)
        del custom.__dict__["_in_play"]
        self.assertEqual([a.id for a in in_play_actors(custom)], [2])

        legacy = self.fixture()
        del legacy.native_global_pv_collections
        legacy.actors[2].hp = 0
        self.assertEqual([a.id for a in in_play_actors(legacy)], [1, 3, 4])
