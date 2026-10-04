import unittest
from types import SimpleNamespace
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_state_level_group import (
    child_level,
    NativeStateLevelGroupHandler,
)


class StateLevelGroupTests(unittest.TestCase):
    def setUp(self):
        self.inv = EffectInvocation(1, 30, 7, 8, (1, 0, 0))
        self.actors = {
            7: SimpleNamespace(state_ledger=SimpleNamespace(entries=[])),
            8: SimpleNamespace(
                state_ledger=SimpleNamespace(
                    entries=[
                        SimpleNamespace(reference=12, level=20),
                        SimpleNamespace(reference=12, level=90),
                    ]
                )
            ),
        }

    def effect(self, parameters):
        raw = [n for value in parameters for n in [value, 0]]
        return dict(effect_class=844, parameters=raw, children=[99]), dict(
            parameters=parameters
        )

    def test_first_matching_state_not_maximum(self):
        e, v = self.effect([0, 0, 1, 0, 1, 0, 12])
        self.assertEqual(child_level(e, v, self.inv, self.actors), 20)

    def test_native_float_factor_plus_integer_constant(self):
        e, v = self.effect([0, 0, 1, 0, 1, 0, 12, 0, 0.5, 3])
        self.assertEqual(child_level(e, v, self.inv, self.actors), 13)

    def test_caster_lookup_absent_default_and_explicit_constant(self):
        e, v = self.effect([0, 0, 1, 0, 1, 0, 12, 1])
        self.assertEqual(child_level(e, v, self.inv, self.actors), 30)
        e, v = self.effect([0, 0, 1, 0, 1, 0, 12, 1, 1, 3])
        self.assertEqual(child_level(e, v, self.inv, self.actors), 3)

    def test_executor_transmits_child_owned_context_and_level(self):
        e, v = self.effect([0, 0, 1, 0, 1, 0, 12])
        calls = []
        h = NativeStateLevelGroupHandler(
            SimpleNamespace(actors=self.actors),
            execute_child=lambda i: calls.append(i) or True,
            group_cells=lambda *a: (),
            actor_position=lambda a: (0, 0, 0),
        )
        self.assertTrue(h(e, v, self.inv))
        self.assertEqual(
            (calls[0].reference, calls[0].level, calls[0].caster_id), (99, 20, 7)
        )
