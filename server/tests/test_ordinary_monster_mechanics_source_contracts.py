"""Native ordinary-monster guards exercised through shared production consumers.

These are source-bound condition/resource contracts. Explicit snapshots below
are unit scenarios, not earned encounter phases or complete paid combats.
"""
import json
from pathlib import Path
import unittest

from wakfu_server.combat_conditions import (
    ConditionActor,
    ConditionCell,
    ConditionContext,
    UnknownCondition,
    evaluate_condition,
)
from wakfu_server.combat_range_conditions import RangeFighter, enemy_count


class OrdinaryMonsterMechanicsSourceContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.native = json.loads(
            (
                Path(__file__).parent
                / "fixtures/ordinary_monster_mechanics_native.json"
            ).read_text()
        )

    def criterion(self, reference):
        return self.native["records"][str(reference)]["data"]["criteria"]

    def hp_context(self, value, maximum=1000, selector="target"):
        return ConditionContext(
            {
                selector: ConditionActor(
                    characteristics={"HP": value},
                    characteristic_maxima={"HP": maximum},
                )
            }
        )

    def enemy_context(self, rows, *, states=()):
        def query(minimum, maximum, selector, aligned, los):
            self.assertEqual(selector, "caster")
            return enemy_count(
                rows,
                affiliation=1,
                center=(0, 0, 0),
                minimum=minimum,
                maximum=maximum,
                aligned=aligned,
                los=los,
            )

        return ConditionContext(
            {"target": ConditionActor(state_ids=frozenset(states))},
            enemy_range_query=query,
        )

    def fighter(self, x, *, affiliation=0, in_play=True, excluded=False, barrel=False):
        return RangeFighter((x, 0, 0), 0, affiliation, in_play, excluded, barrel)

    def test_royal_and_arch_gobball_threshold_uses_target_native_integer_percent(self):
        criterion = self.criterion(182681)
        for hp, expected in ((499, True), (500, True), (509, True), (510, False)):
            with self.subTest(hp=hp):
                self.assertEqual(
                    evaluate_condition(criterion, self.hp_context(hp)), expected
                )
        with self.assertRaises(UnknownCondition):
            evaluate_condition(criterion, self.hp_context(500, selector="caster"))

    def test_royal_and_arch_tofu_count_real_enemy_roster_filters(self):
        criterion = self.criterion(409301)
        first = self.fighter(1)
        rejected = (
            self.fighter(4),
            self.fighter(2, affiliation=1),
            self.fighter(2, in_play=False),
            self.fighter(2, excluded=True),
            self.fighter(2, barrel=True),
        )
        for other in rejected:
            with self.subTest(other=other):
                self.assertFalse(
                    evaluate_condition(criterion, self.enemy_context((first, other)))
                )
        self.assertTrue(
            evaluate_condition(criterion, self.enemy_context((first, self.fighter(3))))
        )
        with self.assertRaises(UnknownCondition):
            evaluate_condition(criterion, ConditionContext({}))

    def test_royal_tofu_disabled_foreign_team_branch_stays_disabled(self):
        context = ConditionContext(
            {
                "triggeringcaster": ConditionActor(fight_affiliation=0),
                "target": ConditionActor(fight_affiliation=1),
            },
            triggering_effect_present=True,
        )
        self.assertFalse(evaluate_condition(self.criterion(182855), context))

    def test_uhu_reaction_keeps_blocking_state_and_minimum_enemy_range(self):
        for distance, expected in ((0, False), (1, True), (2, True), (3, False)):
            context = self.enemy_context((self.fighter(distance),))
            with self.subTest(distance=distance):
                self.assertTrue(evaluate_condition(self.criterion(196760), context))
                self.assertEqual(
                    evaluate_condition(self.criterion(196761), context), expected
                )
        blocked = self.enemy_context((self.fighter(1),), states=(4866,))
        self.assertFalse(evaluate_condition(self.criterion(196760), blocked))

    def test_agonia_phase_is_native_integer_thirty_band_not_exact_hp_equality(self):
        outer, producer = self.criterion(248379), self.criterion(248467)
        for hp, outer_expected, producer_expected in (
            (290, True, False),
            (300, True, True),
            (309, True, True),
            (310, False, False),
        ):
            with self.subTest(hp=hp):
                context = self.hp_context(hp, selector="caster")
                self.assertEqual(evaluate_condition(outer, context), outer_expected)
                self.assertEqual(
                    evaluate_condition(producer, context), producer_expected
                )

    def test_native_plant_and_summon_producers_share_free_cell_guards(self):
        # Real349 roots: Xecordagovasme4750/4751 and native plant area196.
        for reference in (151349, 151347, 151351, 151353, 240395, 412418, 412382):
            criterion = self.criterion(reference)
            for cell, expected in (
                (ConditionCell(True, False), True),
                (ConditionCell(False, False), False),
                (ConditionCell(True, True), False),
                (ConditionCell(True, False, (True,)), False),
                (ConditionCell(True, False, (False,)), True),
            ):
                with self.subTest(reference=reference, cell=cell):
                    self.assertEqual(
                        evaluate_condition(criterion, ConditionContext({}, cell)),
                        expected,
                    )
            with self.assertRaises(UnknownCondition):
                evaluate_condition(criterion, ConditionContext({}))
        # Agonia's actual strict349 additionally rejects nonblocking occupants.
        self.assertFalse(
            evaluate_condition(
                self.criterion(248443),
                ConditionContext({}, ConditionCell(True, False, (False,))),
            )
        )

    def test_jalalinea_form_branch_uses_native_twenty_percent_boundary(self):
        for hp, high_expected in ((190, False), (199, False), (200, True), (209, True)):
            for high, low in ((328824, 328825), (327545, 328820)):
                with self.subTest(hp=hp, high=high):
                    context = self.hp_context(hp)
                    self.assertEqual(
                        evaluate_condition(self.criterion(high), context), high_expected
                    )
                    self.assertEqual(
                        evaluate_condition(self.criterion(low), context),
                        not high_expected,
                    )

    def test_white_miaumiau_native_heal_applies_resources_and_wire_without_overflow(
        self,
    ):
        from wakfu_server.combat_state import Actor, Fight
        from wakfu_server.combat_healing_handler import (
            NativeHealingHandler,
            HealingExecutionContext,
        )
        from wakfu_server.combat_effect_dispatch import EffectInvocation
        from wakfu_server.combat_effect_removal import _identity_fields

        effect = self.native["full_native_effects"]["64488"]
        self.assertEqual(effect["effect_class"], 258)
        for hp, expected_delta in ((90, 10), (97, 3), (100, 0)):
            with self.subTest(hp=hp):
                source = Actor(7, 0, (0, 0, 0), 100, 6, 3, 10, 1, 3, True)
                target = Actor(-7, 0, (1, 0, 0), hp, 6, 3, 5, 1, max_hp=100)
                enemy = Actor(-8, 1, (2, 0, 0), 100, 6, 3, 4, 1)
                fight = Fight(
                    77,
                    [source, target, enemy],
                    {source.position, target.position, enemy.position},
                    {0: {source.position, target.position}, 1: {enemy.position}},
                )
                fight.ready(3)
                for actor in (source, target):
                    actor.effect_stats = {92: 0, 97: 0, 100: 0, 32: 0}
                    actor.effect_maxima = {92: 0}
                    actor.effect_frozen = frozenset()
                    actor.physical_radius = 0
                packets = []
                context = HealingExecutionContext(
                    False, True, False, False, 0, 0, True, 0, 1000, True
                )
                handler = NativeHealingHandler(
                    fight,
                    packets,
                    action_id=1,
                    allocate_uid=lambda: 99,
                    context=lambda *args: context,
                    rng=lambda: 0.99,
                )
                invocation = EffectInvocation(
                    64488, 1, 7, -7, target.position, base_uid=80
                )
                self.assertTrue(handler(effect, {}, invocation))
                self.assertEqual(target.hp - hp, expected_delta)
                self.assertLessEqual(target.hp, target.max_hp)
                self.assertEqual(target.effect_stats[92], 0)
                self.assertEqual(len(packets), 1)
                fields = _identity_fields(packets[0][1][19:])
                self.assertEqual((fields[3], fields[4]), (64488, expected_delta))


if __name__ == "__main__":
    unittest.main()
