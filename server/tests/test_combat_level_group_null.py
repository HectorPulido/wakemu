"""eYm preserves parent evaluation when its level-source PV is null."""
import unittest
from types import SimpleNamespace
from wakfu_server.combat_level_group import runtime_group_level
from wakfu_server.combat_effect_dispatch import EffectInvocation


class LevelGroupNullTests(unittest.TestCase):
    def test_null_target_preserves_parent_level_and_unknown_identity_rejects(self):
        effect = dict(
            parameters=[0, 0] * 8,
            native_effect_flags=[],
            native_execution_mode=2,
            native_definition_class="eVy",
            native_timing_definition=dict(
                clock_on_caster=False,
                clock_on_target=True,
                ryE=0,
                ryF=0.0,
                ryG=False,
                ryH=0,
                ryI=0.0,
                esr=False,
            ),
        )
        values = dict(parameters=[0, 0, 0, 0, 0, 0, 0, 100])
        invocation = EffectInvocation(371570, 37, 7, None, (0, 0, 0))
        self.assertEqual(
            runtime_group_level(
                effect, values, invocation, {7: SimpleNamespace(effective_level=200)}
            ),
            37,
        )
        invocation = EffectInvocation(371570, 37, 7, 999, (0, 0, 0))
        self.assertEqual(
            runtime_group_level(
                effect,
                values,
                invocation,
                {7: SimpleNamespace(effective_level=200)},
                non_actor_ids=(999,),
            ),
            37,
        )
        with self.assertRaisesRegex(ValueError, "group level actor"):
            runtime_group_level(
                effect, values, invocation, {7: SimpleNamespace(effective_level=200)}
            )
