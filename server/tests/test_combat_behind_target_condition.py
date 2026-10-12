"""Native eNA direction oracle and actual registered QI occupancy."""
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from wakfu_server.combat_conditions import (
    ConditionContext,
    evaluate_condition,
    UnknownCondition,
)
from wakfu_server.combat_behind_target_condition import (
    native_behind_target_point,
    native_behind_target_free,
)
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_qi_fight import (
    prepare_fresh_actor_slots,
    install_fresh_actor_slots,
)


class BehindTargetConditionTests(unittest.TestCase):
    def test_installed_direction_oracle_keeps_diagonals_and_int32_overflow(self):
        path = (
            Path(__file__).resolve().parents[1]
            / "test-fixtures/combat/behind-target-direction.json"
        )
        for row in json.loads(path.read_text()):
            self.assertEqual(
                native_behind_target_point(row["origin"], row["direction"]),
                tuple(row["point"]),
            )

    def test_predicate_requires_actual_typed_callback_and_no_arguments(self):
        for value in (False, True):
            self.assertIs(
                evaluate_condition(
                    "IsCellBehindTargetFree()",
                    ConditionContext(actors={}, behind_target_free_query=lambda: value),
                ),
                value,
            )
        for context in (
            ConditionContext(actors={}),
            ConditionContext(actors={}, behind_target_free_query=lambda: 1),
        ):
            with self.assertRaises(UnknownCondition):
                evaluate_condition("IsCellBehindTargetFree()", context)
        with self.assertRaises(UnknownCondition):
            evaluate_condition(
                "IsCellBehindTargetFree(1)",
                ConditionContext(actors={}, behind_target_free_query=lambda: True),
            )

    def fixture(self, caster_cell=(-8, -7, -1), radius=0):
        caster = Actor(-200, 1, caster_cell, 100, 6, 3, 1, 53)
        target = Actor(7, 0, (-5, -7, -1), 100, 6, 3, 1, 53)
        caster.physical_radius = radius
        target.physical_radius = 0
        target.direction = 1
        cells = {
            (x, y, z) for x in range(-10, -2) for y in range(-9, -3) for z in (-1, 2)
        }
        fight = Fight(
            99, [caster, target], cells, {0: {target.position}, 1: {caster.position}}
        )
        fight.native_qi_snapshot = dict(
            x=-10, y=-9, width=8, height=6, cell_masks=[256] * 48
        )
        install_fresh_actor_slots(
            fight, prepare_fresh_actor_slots(fight, physical_radii={-200: radius, 7: 0})
        )
        return fight, caster, target

    @staticmethod
    def authority(fight, actor):
        if fight.actors.get(actor.id) is not actor:
            raise ValueError("Unknown actual actor")
        return SimpleNamespace(targeting={"is_eGj": True})

    def test_actual_registered_footprint_blocks_behind_cell_across_z(self):
        fight, caster, target = self.fixture()
        self.assertTrue(
            native_behind_target_free(fight, caster, target, self.authority)
        )
        fight, caster, target = self.fixture(caster_cell=(-7, -7, 2), radius=1)
        self.assertFalse(
            native_behind_target_free(fight, caster, target, self.authority)
        )
        target.native_forced_direction = 5  # eNA reads bcy, never pGJ.
        self.assertFalse(
            native_behind_target_free(fight, caster, target, self.authority)
        )

    def test_missing_qi_or_direction_fails_closed_and_null_target_is_false(self):
        fight, caster, target = self.fixture()
        self.assertFalse(native_behind_target_free(fight, caster, None, self.authority))
        target.direction = None
        with self.assertRaises(ValueError):
            native_behind_target_free(fight, caster, target, self.authority)
        target.direction = 1
        del fight.native_qi_slots
        with self.assertRaises(ValueError):
            native_behind_target_free(fight, caster, target, self.authority)

    def test_proven_non_fighter_source_returns_false_before_cell_queries(self):
        self.assertFalse(
            native_behind_target_free(
                object(),
                object(),
                object(),
                lambda fight, actor: SimpleNamespace(targeting={"is_eGj": False}),
            )
        )
