from copy import deepcopy
import json
import unittest
from pathlib import Path
from wakfu_server.combat_level_group import (
    NativeLevelGroupHandler,
    level_group_override,
)
from wakfu_server.combat_definitions import effect_profile
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_level_group import runtime_group_level
from types import SimpleNamespace
from wakfu_server import native_catalog


class NativeLevelGroupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.effects = json.loads(
            native_catalog.read_text(
                Path(__file__).parents[1] / "protocol/spell-effect-trees.json"
            )
        )["effects"]

    def test_real_catalog_linear_fractional_float_parameters(self):
        self.assertEqual(level_group_override(self.effects["368107"], 1, 200), 200)
        self.assertEqual(level_group_override(self.effects["379594"], 10, 200), 249)
        self.assertEqual(level_group_override(self.effects["379596"], 1, 200), 156)

    def test_runtime_event_flags_preserve_level_and_require_fight_context(self):
        effect = deepcopy(self.effects["368107"])
        invocation = EffectInvocation(368107, 1, 7, -7, (4, 0, 0))
        actors = {
            7: SimpleNamespace(effective_level=200),
            -7: SimpleNamespace(effective_level=20),
        }
        effect["native_effect_flags"] = [1, 17]
        values = effect_profile(effect, 1)
        self.assertEqual(
            runtime_group_level(effect, values, invocation, actors, active=True), 200
        )
        for active in (None, False):
            with self.assertRaises(ValueError):
                runtime_group_level(effect, values, invocation, actors, active=active)
        effect["native_effect_flags"] = [999]
        with self.assertRaisesRegex(ValueError, "Unaudited"):
            runtime_group_level(effect, values, invocation, actors, active=True)

    def test_native_jar_integer_ratio_overflow_and_floor(self):
        effect = deepcopy(self.effects["368107"])
        for actor, ratio, base, growth, expected in [
            (101, 33, 0, 1, 33),
            (-101, 33, 0, 1, -33),
            (101, 33, 6.25, 0.75, 31),
            (101, 33, 0, -0.1, -4),
            (32767, 2147483647, 0, 1, -21300),
        ]:
            effect["parameters"][14] = ratio
            effect["parameters"][16] = base
            effect["parameters"][18] = growth
            self.assertEqual(level_group_override(effect, 1, actor), expected)

    def test_override_minus_one_preserves_container_and_short_wrap(self):
        effect = deepcopy(self.effects["368107"])
        effect["parameters"][16] = -1
        effect["parameters"][18] = 0
        self.assertEqual(level_group_override(effect, 12, 200), 12)
        effect["parameters"][16] = 65538
        self.assertEqual(level_group_override(effect, 12, 200), 2)

    def test_runtime_preserves_native_signed_negative_child_level(self):
        effect = deepcopy(self.effects["368107"])
        effect["parameters"][16] = -4
        effect["parameters"][18] = 0
        invocation = EffectInvocation(368107, 1, 7, -7, (4, 0, 0))
        actors = {
            7: SimpleNamespace(effective_level=200),
            -7: SimpleNamespace(effective_level=20),
        }
        self.assertEqual(
            runtime_group_level(
                effect, effect_profile(effect, 1), invocation, actors, active=True
            ),
            -4,
        )

    def test_real_group_children_use_actor_level_keep_identity(self):
        effect = self.effects["368107"]
        calls = []
        handler = NativeLevelGroupHandler(
            execute_child=lambda i: calls.append(i) or True,
            actor_level=lambda actor: 200 if actor == 7 else 20,
            actor_position=lambda actor: (0, 0, 0),
            group_cells=lambda e, i: [],
        )
        invocation = EffectInvocation(
            368107, 1, 7, -7, (4, 0, 0), base_uid=80, state_uid=81
        )
        self.assertTrue(handler(effect, effect_profile(effect, 1), invocation))
        self.assertEqual(
            calls,
            [
                EffectInvocation(
                    368109, 200, 7, -7, (4, 0, 0), base_uid=80, state_uid=81
                )
            ],
        )

    def test_level_actor_selection_occurs_after_native_rebind(self):
        effect = deepcopy(self.effects["368107"])
        effect["parameters"][10] = 2
        calls = []
        reads = []
        handler = NativeLevelGroupHandler(
            execute_child=lambda i: calls.append(i) or True,
            actor_level=lambda actor: reads.append(actor) or 50,
            actor_position=lambda actor: (0, 0, 0),
            group_cells=lambda e, i: [],
        )
        self.assertTrue(
            handler(
                effect,
                effect_profile(effect, 1),
                EffectInvocation(368107, 1, 7, -7, (4, 0, 0)),
            )
        )
        self.assertEqual(reads, [-7])
        self.assertEqual(calls[0].caster_id, -7)
        self.assertEqual(calls[0].target_id, 7)
        self.assertEqual(calls[0].level, 50)

    def test_failure_and_unknown_relative_probability(self):
        effect = deepcopy(self.effects["368107"])
        calls = []
        handler = NativeLevelGroupHandler(
            execute_child=lambda i: calls.append(i) or False,
            actor_level=lambda actor: 200,
            actor_position=lambda actor: (0, 0, 0),
            group_cells=lambda e, i: [],
        )
        invocation = EffectInvocation(368107, 1, 7, -7, (4, 0, 0))
        self.assertFalse(handler(effect, effect_profile(effect, 1), invocation))
        effect["parameters"][6] = 1
        with self.assertRaisesRegex(ValueError, "Relative"):
            handler(effect, effect_profile(effect, 1), invocation)
        self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
