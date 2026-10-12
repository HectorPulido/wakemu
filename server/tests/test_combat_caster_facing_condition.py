"""Installed eNz vectors and actual registered fighter footprint lookup."""
import json
from pathlib import Path
import unittest
import test_combat_behind_target_condition as behind_fixture
from wakfu_server.combat_conditions import (
    ConditionContext,
    evaluate_condition,
    UnknownCondition,
)
from wakfu_server.combat_caster_facing_condition import (
    native_caster_facing_point,
    native_caster_facing_fighter,
)


class CasterFacingConditionTests(unittest.TestCase):
    def test_installed_vector_oracle_including_diagonals_and_overflow(self):
        path = (
            Path(__file__).resolve().parents[1]
            / "test-fixtures/combat/caster-facing-direction.json"
        )
        for row in json.loads(path.read_text()):
            self.assertEqual(
                native_caster_facing_point(row["origin"], row["direction"]),
                tuple(row["point"]),
            )

    def test_predicate_zero_arguments_and_strict_authority(self):
        for value in (False, True):
            context = ConditionContext(
                actors={}, caster_facing_fighter_query=lambda: value
            )
            self.assertIs(evaluate_condition("IsCasterFacingFighter()", context), value)
        for callback in (None, lambda: 1):
            with self.assertRaises(UnknownCondition):
                evaluate_condition(
                    "IsCasterFacingFighter()",
                    ConditionContext(actors={}, caster_facing_fighter_query=callback),
                )
        with self.assertRaises(UnknownCondition):
            evaluate_condition(
                "IsCasterFacingFighter(1)",
                ConditionContext(actors={}, caster_facing_fighter_query=lambda: True),
            )

    def test_lookup_uses_actual_xy_footprint_across_altitude(self):
        fixture = behind_fixture.BehindTargetConditionTests()
        fight, caster, target = fixture.fixture(caster_cell=(-7, -7, 2))
        caster.direction = 1
        # Ahead is -6,-7. Target center is -5,-7, radius0: no fighter.
        self.assertFalse(native_caster_facing_fighter(fight, caster, fixture.authority))
        # Construct a fresh fight whose target footprint covers ahead across Z.
        from wakfu_server.combat_state import Actor, Fight
        from wakfu_server.combat_qi_fight import (
            prepare_fresh_actor_slots,
            install_fresh_actor_slots,
        )

        caster = Actor(-200, 1, (-7, -7, 2), 100, 6, 3, 1, 53)
        target = Actor(7, 0, (-5, -7, -1), 100, 6, 3, 1, 53)
        caster.direction = 1
        caster.physical_radius = 0
        target.physical_radius = 1
        fight = Fight(
            100,
            [caster, target],
            fight.walkable,
            {0: {target.position}, 1: {caster.position}},
        )
        fight.native_qi_snapshot = dict(
            x=-10, y=-9, width=8, height=6, cell_masks=[256] * 48
        )
        install_fresh_actor_slots(
            fight,
            prepare_fresh_actor_slots(
                fight, physical_radii={caster.id: 0, target.id: 1}
            ),
        )
        self.assertTrue(native_caster_facing_fighter(fight, caster, fixture.authority))
        caster.direction = 5
        self.assertFalse(native_caster_facing_fighter(fight, caster, fixture.authority))

    def test_caster_own_registered_extent_is_not_excluded(self):
        fixture = behind_fixture.BehindTargetConditionTests()
        fight, caster, target = fixture.fixture(radius=1)
        caster.direction = 1
        self.assertTrue(native_caster_facing_fighter(fight, caster, fixture.authority))
        caster.direction = None
        with self.assertRaises(ValueError):
            native_caster_facing_fighter(fight, caster, fixture.authority)

    def test_missing_registry_or_caster_authority_is_not_a_false_result(self):
        fixture = behind_fixture.BehindTargetConditionTests()
        fight, caster, target = fixture.fixture()
        caster.direction = 1
        with self.assertRaises(ValueError):
            native_caster_facing_fighter(fight, None, fixture.authority)
        del fight.native_qi_slots
        with self.assertRaises(ValueError):
            native_caster_facing_fighter(fight, caster, fixture.authority)
