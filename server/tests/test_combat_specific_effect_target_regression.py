"""Read-only unit contract probes for eII.b/eMj HasEffectWithSpecificId."""
from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SERVER = ROOT / "server"
from wakfu_server.combat.combat_conditions import (
    ConditionActor,
    ConditionContext,
    UnknownCondition,
    evaluate_condition,
)
import wakfu_server.combat.combat_conditions as conditions
from unittest.mock import patch

# This expression has no characteristic aliases. Avoid loading native catalog
# data in these isolated tests; native operand parsing remains under test.


CRITERION = 'HasEffectWithSpecificId("target", 346456)'


class SpecificEffectNativeTargetCandidateTests(unittest.TestCase):
    def evaluate_target(self, actor):
        with patch.object(conditions, "canonical_aliases", return_value={}):
            return evaluate_condition(
                CRITERION,
                ConditionContext(
                    actors={"target": actor},
                    effect_target_absent=False,
                ),
            )

    def test_non_ehg_q_q_target_is_native_null_result(self):
        # A plain Qq has no eHg.bax(); eII returns null and eMj returns -1.
        actor = ConditionActor(
            actor_id=28,
            is_native_fighter=False,
            is_native_ehg=False,
            retained_effect_ids=None,
        )
        self.assertFalse(self.evaluate_target(actor))

    def test_fa_v_area_without_qf_is_false(self):
        # faV is eHg, but bax() can still be null when no Qf manager exists.
        actor = ConditionActor(
            actor_id=28,
            is_native_fighter=False,
            is_native_ehg=True,
            retained_effect_ids=frozenset(),
        )
        self.assertFalse(self.evaluate_target(actor))

    def test_manager_backed_area_uses_complete_retained_effects(self):
        actor = ConditionActor(
            actor_id=28,
            is_native_fighter=False,
            is_native_ehg=True,
            retained_effect_ids=frozenset({346456}),
        )
        self.assertTrue(self.evaluate_target(actor))

    def test_manager_backed_area_missing_population_stays_unknown(self):
        actor = ConditionActor(
            actor_id=28,
            is_native_fighter=False,
            is_native_ehg=True,
            retained_effect_ids=None,
        )
        with self.assertRaises(UnknownCondition):
            self.evaluate_target(actor)

    def test_unclassified_area_with_missing_population_stays_unknown(self):
        # A missing kind flag is not proof of either a plain Qq or an eHg.
        # Keep incomplete native authority fail-closed until its manager type
        # is known.
        actor = ConditionActor(
            actor_id=28,
            is_native_fighter=False,
            is_native_ehg=None,
            retained_effect_ids=None,
        )
        with self.assertRaises(UnknownCondition):
            self.evaluate_target(actor)

    def test_real_fighter_missing_qf_population_stays_unknown(self):
        actor = ConditionActor(
            actor_id=-7,
            is_native_fighter=True,
            is_native_ehg=True,
            retained_effect_ids=None,
        )
        with self.assertRaises(UnknownCondition):
            self.evaluate_target(actor)

    def test_selected_cell_occupant_uses_its_complete_qf(self):
        # When QI/eII has resolved the cell to its actual occupant, the
        # criterion consumes that fighter's retained Qf, not cell metadata.
        actor = ConditionActor(
            actor_id=-7,
            is_native_fighter=True,
            is_native_ehg=True,
            retained_effect_ids=frozenset({346456}),
        )
        self.assertTrue(self.evaluate_target(actor))

    def test_proven_null_target_is_false(self):
        result = evaluate_condition(
            CRITERION,
            ConditionContext(actors={}, effect_target_absent=True),
        )
        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main(verbosity=2)
