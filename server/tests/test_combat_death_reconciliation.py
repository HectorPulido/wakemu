"""Preserve native extra-turn occurrences during ordinary death settlement."""
from types import SimpleNamespace
import unittest

from wakfu_server.combat_additional_turn import additional_turn_insertion
from wakfu_server.combat_death_reconciliation import (
    apply_death_reconciliation,
    prepare_death_reconciliation,
)


class DeathReconciliationOccurrenceTests(unittest.TestCase):
    def fight(self, order, current, *, retired=()):
        actors = {
            identity: SimpleNamespace(id=identity, team=0 if identity == 7 else 1)
            for identity in order
        }
        fight = SimpleNamespace(
            order=list(order),
            turn_index=current,
            actors=actors,
            rift_wave_state=None,
            turn_id=10,
            phase="active",
            winner=None,
            native_base_turn_order=list(dict.fromkeys(order)),
            native_timeline_round=1,
            begins=0,
        )
        fight._in_play = lambda actor: actor.id not in retired

        def begin():
            fight.begins += 1

        fight._begin_turn = begin
        fight._event = lambda *args, **kwargs: None
        return fight

    def settle(self, fight):
        plan = prepare_death_reconciliation(fight)
        apply_death_reconciliation(fight, plan)
        return plan

    def test_no_deaths_preserves_each_repeated_current_occurrence(self):
        order = [7, -200, 7, 65, 7]
        for index in range(len(order)):
            with self.subTest(index=index):
                fight = self.fight(order, index)
                self.settle(fight)
                self.assertEqual(fight.order, order)
                self.assertEqual(fight.turn_index, index)
                self.assertEqual(fight.turn_id, 10)
                self.assertEqual(fight.begins, 0)

    def test_retirement_before_current_preserves_filtered_occurrence(self):
        fight = self.fight([52, 7, -200, 7, 65], 3, retired=(52,))
        base = list(fight.native_base_turn_order)
        self.settle(fight)
        self.assertEqual(fight.order, [7, -200, 7, 65])
        self.assertEqual(fight.turn_index, 2)
        self.assertEqual(fight.native_base_turn_order, base)
        self.assertEqual(fight.begins, 0)

    def test_retirement_after_current_does_not_move_cursor(self):
        fight = self.fight([7, -200, 7, 65], 2, retired=(65,))
        self.settle(fight)
        self.assertEqual(fight.order, [7, -200, 7])
        self.assertEqual(fight.turn_index, 2)

    def test_retired_repeated_current_selects_successor_after_actual_occurrence(self):
        # Actor65 preserves the opposing team while retired7 leaves players52.
        fight = self.fight([7, 52, 7, -200, 52, 65], 2, retired=(7,))
        fight.actors[52].team = 0
        self.settle(fight)
        self.assertEqual(fight.order, [52, -200, 52, 65])
        self.assertEqual(fight.turn_index, 1)
        self.assertEqual(fight.order[fight.turn_index], -200)
        self.assertEqual(fight.turn_id, 11)
        self.assertEqual(fight.begins, 1)

    def test_retired_current_wraps_to_existing_first_survivor(self):
        fight = self.fight([52, 7, -200, 7], 3, retired=(7,))
        fight.actors[52].team = 0
        self.settle(fight)
        self.assertEqual(fight.order, [52, -200])
        self.assertEqual(fight.turn_index, 0)
        self.assertEqual(fight.turn_id, 11)
        self.assertEqual(fight.begins, 1)

    def test_real_additional_turn_insertion_survives_repeated_settlement(self):
        insertion = additional_turn_insertion(
            [7, -200, 65],
            0,
            mode=0,
            offset=2,
            caster_id=7,
            target_id=7,
        )
        self.assertTrue(insertion["applied"])
        fight = self.fight(insertion["order"], insertion["insertion"])
        base = [7, -200, 65]
        fight.native_base_turn_order = list(base)
        for _ in range(3):
            self.settle(fight)
        self.assertEqual(fight.turn_index, insertion["insertion"])
        self.assertEqual(fight.order, insertion["order"])
        self.assertEqual(fight.native_base_turn_order, base)

    def test_terminal_team_settlement_still_finishes_without_successor(self):
        fight = self.fight([7, -200, 7], 2, retired=(-200,))
        self.settle(fight)
        self.assertEqual(fight.phase, "finished")
        self.assertEqual(fight.winner, 0)
        self.assertEqual(fight.begins, 0)
