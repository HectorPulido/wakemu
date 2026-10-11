"""Fresh criterion selection is qualified for each actor-rebinding route."""
import unittest
from wakfu_server.combat_effect_dispatch import EffectDispatcher, EffectInvocation
from wakfu_server.combat_conditions import ConditionContext
from test_combat_effect_dispatch import effect


class RebindFreshPolicyTests(unittest.TestCase):
    def test_only_actor_rebinding_marks_fresh_child_context(self):
        for mode, expected_caster, expected_target, fresh in (
            (0, 7, 8, False),
            (1, 8, 8, True),
            (2, 8, 7, True),
        ):
            with self.subTest(mode=mode):
                seen = []
                dispatcher = EffectDispatcher(
                    {
                        "90": effect(330, (0, 0, 1, 0, 1, mode), children=(91,)),
                        "91": effect(400),
                    },
                    {
                        400: lambda definition, values, invocation: seen.append(
                            invocation
                        )
                        or True
                    },
                    resolve=lambda definition, invocation: (invocation,),
                    condition_context=lambda invocation: ConditionContext({}),
                    probability_accepts=lambda *args: True,
                    group_cells=lambda *args: (),
                    actor_position=lambda identity: (identity, 1, 0),
                )
                self.assertTrue(
                    dispatcher.execute(EffectInvocation(90, 20, 7, 8, (8, 1, 0)))
                )
                self.assertEqual(len(seen), 1)
                self.assertEqual(
                    (seen[0].caster_id, seen[0].target_id),
                    (expected_caster, expected_target),
                )
                self.assertIs(seen[0].wakemu_rebound_child_selection, fresh)

    def test_only_changed_relationship_selection_marks_mode_zero_context(self):
        from dataclasses import replace

        for mask, selected_target, fresh in (
            ((1 << 42), 9, True),
            ((1 << 42), 8, False),
            (1, 9, False),
        ):
            with self.subTest(mask=mask, selected_target=selected_target):
                seen = []
                group = effect(330, (0, 0, 1, 0, 1, 0), children=(91,))
                group["native_target_selector"] = {"class": "fcE", "mask": mask}
                dispatcher = EffectDispatcher(
                    {"90": group, "91": effect(400)},
                    {
                        400: lambda definition, values, invocation: seen.append(
                            invocation
                        )
                        or True
                    },
                    resolve=lambda definition, invocation: (
                        replace(invocation, target_id=selected_target)
                        if invocation.reference == 90
                        else invocation,
                    ),
                    condition_context=lambda invocation: ConditionContext({}),
                    probability_accepts=lambda *args: True,
                    group_cells=lambda *args: (),
                    actor_position=lambda identity: (identity, 1, 0),
                )
                self.assertTrue(
                    dispatcher.execute(EffectInvocation(90, 20, 7, 8, (8, 1, 0)))
                )
                self.assertEqual(len(seen), 1)
                self.assertEqual(
                    (seen[0].caster_id, seen[0].target_id), (7, selected_target)
                )
                self.assertIs(seen[0].wakemu_rebound_child_selection, fresh)
