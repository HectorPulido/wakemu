"""Qe.k reflection clones execute without becoming another retained listener."""
from copy import deepcopy
from dataclasses import replace
import unittest

import test_combat_reflect_runner as reflection_fixture
from wakfu_server.combat_effect_dispatch import EffectDispatcher
from wakfu_server.combat_effect_removal import _identity_fields
from wakfu_server.combat_final_modifier import final_modifier_source
from wakfu_server.combat_runner_target import runner_target_invocation


class ReflectionCloneLifecycleTests(unittest.TestCase):
    def fixture(self):
        values = reflection_fixture.ReflectRunnerTests().fixture()
        (
            fight,
            packets,
            phases,
            handler,
            effect,
            invocation,
            source,
            runner,
            original,
        ) = values
        invocation = replace(invocation, base_uid=77, state_uid=70)
        listener = dict(
            uid=77,
            effect_class=309,
            state_uid=70,
            execution_count=-1,
            invocation=dict(vars(invocation)),
        )
        fight.native_owned_group_effects = {77: listener}
        effect.update(
            parameter_count=0,
            probability_base=100,
            probability_per_level=0,
            minimum_level=1,
            maximum_level=200,
            children=[],
            criteria="",
        )
        handler.allocate_uid = lambda: self.fail(
            "Activation discarded the allocated clone UID"
        )
        handler.event_lifecycle.register_applied = lambda *args: self.fail(
            "Activated reflection was registered as another retained listener"
        )
        dispatcher = EffectDispatcher(
            {"76294": effect},
            {309: handler},
            resolve=lambda effect, selected: (selected,),
            condition_context=lambda selected: None,
            probability_accepts=lambda probability, selected: True,
            group_cells=lambda *args: (),
            actor_position=lambda actor: (0, 0, 0),
        )
        return (
            fight,
            packets,
            phases,
            handler,
            effect,
            invocation,
            source,
            runner,
            original,
            dispatcher,
        )

    def test_repeated_activation_preserves_listener_and_exact_clone_uid(self):
        (
            fight,
            packets,
            phases,
            handler,
            effect,
            invocation,
            source,
            runner,
            original,
            dispatcher,
        ) = self.fixture()
        before = deepcopy(fight.native_owned_group_effects)
        with final_modifier_source(source):
            for uid in (901, 902):
                self.assertTrue(
                    dispatcher.execute_activation(
                        invocation,
                        source=source,
                        condition_context=lambda *args: None,
                        executable=True,
                        allocate_uid=lambda uid=uid: uid,
                    )
                )
        self.assertEqual(fight.native_owned_group_effects, before)
        self.assertFalse(fight.owned_stat_effects)
        self.assertEqual(
            [
                _identity_fields(body[18:])[1]
                for opcode, body in packets
                if opcode == 13497
            ],
            [901, 902],
        )
        self.assertEqual(phases, [1, 2, 3, 4] * 2)
        self.assertEqual(runner_target_invocation(runner, original).cell, (4, 5, 6))
        self.assertFalse(handler.runners)
        self.assertFalse(handler.prepared)
        self.assertFalse(handler.prepared_event_clones)

    def test_missing_or_mismatched_original_listener_rejects_before_mutation(self):
        for field, value in (
            ("uid", 78),
            ("effect_class", 400),
            ("state_uid", 71),
            ("invocation", {"reference": 1, "level": 200}),
            ("invocation", None),
        ):
            with self.subTest(field=field, value=value):
                (
                    fight,
                    packets,
                    phases,
                    handler,
                    effect,
                    invocation,
                    source,
                    runner,
                    original,
                    dispatcher,
                ) = self.fixture()
                fight.native_owned_group_effects[77][field] = value
                with self.assertRaisesRegex(ValueError, "original listener authority"):
                    handler.prepare_activation(effect, {}, invocation, clone_uid=901)
                self.assertFalse(packets)
                self.assertFalse(phases)
                self.assertFalse(handler.prepared_event_clones)
                self.assertFalse(fight.owned_stat_effects)


if __name__ == "__main__":
    unittest.main()
