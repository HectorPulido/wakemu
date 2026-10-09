"""Production adapter owns the actual roster, independently of profile catalogs."""
from dataclasses import replace
import unittest
import test_combat_runtime_adapter as fixture_module
from wakfu_server.characters.captured_roster import (
    CapturedCreature,
    OwnedCapturedRoster,
)
from wakfu_server.combat_conditions import evaluate_condition, UnknownCondition
from wakfu_server.combat_effect_dispatch import EffectInvocation


class BreedInSymbiotAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture_module.ServerAdapterTests.setUpClass()

    def test_actual_adapter_component_empty_occupied_unavailable_and_unknown(self):
        fixture = fixture_module.ServerAdapterTests()
        fixture.setUp()
        base_authority = fixture.adapter.actor_authority
        occupied = OwnedCapturedRoster(
            7, (CapturedCreature(0, 5347, ""),) + (None,) * 9, (False,) * 10
        )
        for typed, roster, expected in (
            (True, OwnedCapturedRoster(7), False),
            (True, occupied, True),
            (False, None, False),
            (True, None, None),
            (None, None, None),
        ):
            with self.subTest(typed=typed, occupied=roster is occupied):

                def authority(preview, actor):
                    return replace(
                        base_authority(preview, actor),
                        native_is_ehp=typed,
                        native_captured_roster=roster,
                    )

                fixture.adapter.actor_authority = authority
                context = fixture.adapter.condition(
                    fixture.preview,
                    {},
                    None,
                    EffectInvocation(326382, 200, 7, 7, (0, 0, 0)),
                )
                expression = 'HasBreedInSymbiot(5347, "caster")'
                if expected is None:
                    with self.assertRaises(UnknownCondition):
                        evaluate_condition(expression, context)
                else:
                    self.assertEqual(evaluate_condition(expression, context), expected)
                self.assertFalse(
                    evaluate_condition('HasBreedInSymbiot(0, "caster")', context)
                )

    def test_target_selector_reads_target_component_and_unknown_selector_is_null(self):
        fixture = fixture_module.ServerAdapterTests()
        fixture.setUp()
        base_authority = fixture.adapter.actor_authority
        slots = (CapturedCreature(0, 5347, ""),) + (None,) * 9

        def authority(preview, actor):
            return replace(
                base_authority(preview, actor),
                native_is_ehp=True,
                native_captured_roster=OwnedCapturedRoster(
                    actor.id, slots, (False,) * 10
                ),
            )

        fixture.adapter.actor_authority = authority
        context = fixture.adapter.condition(
            fixture.preview, {}, None, EffectInvocation(326382, 200, 7, 8, (0, 0, 0))
        )
        self.assertTrue(
            evaluate_condition('HasBreedInSymbiot(5347, " TARGET ")', context)
        )
        self.assertFalse(
            evaluate_condition('HasBreedInSymbiot(5347, "unrecognized")', context)
        )


if __name__ == "__main__":
    unittest.main()
