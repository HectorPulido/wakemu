from copy import deepcopy
from test_combat_effect_runtime import NativeRuntimeFactoryTests
from wakfu_server.combat_effect_dispatch import EffectInvocation


class StateLevelGroupRuntimeTests(NativeRuntimeFactoryTests):
    def test_actual844_tree346173_transmits_owned_state7649_level(self):
        preview = deepcopy(self.fight)
        target = preview.actors[7]
        target.state_ledger.apply(
            self.states, 7649, 3, caster_id=7, uid=100, applying_effect_has_delay=False
        )
        dispatcher, packets = self.factory()(preview, {})
        observed = []
        native_stat = dispatcher.handlers[self.effects["346174"]["effect_class"]]

        def record(effect, values, invocation):
            observed.append(invocation.level)
            return native_stat(effect, values, invocation)

        dispatcher.handlers[self.effects["346174"]["effect_class"]] = record
        dispatcher.execute(EffectInvocation(346173, 1, 7, 7, (0, 0, 0)))
        self.assertEqual(observed, [3])
        self.assertTrue(packets)

    def test_actual999_tree379594_uses_native_float249(self):
        preview = deepcopy(self.fight)
        preview.actors[7].effective_level = 200
        dispatcher, packets = self.factory()(preview, {})
        observed = []
        native_state = dispatcher.handlers[304]

        def record(effect, values, invocation):
            observed.append(invocation.level)
            return native_state(effect, values, invocation)

        dispatcher.handlers[304] = record
        from wakfu_server.combat_level_group import runtime_group_level
        from wakfu_server.combat_definitions import effect_profile

        effect = self.effects["379594"]
        inv = EffectInvocation(379594, 10, 7, 7, (0, 0, 0))
        self.assertEqual(
            runtime_group_level(
                effect, effect_profile(effect, 10), inv, preview.actors
            ),
            249,
        )
        self.assertFalse(dispatcher.execute(inv))  # Native parent maximum_level is5.
        self.assertEqual(observed, [])
        dispatcher.execute(EffectInvocation(379594, 5, 7, 7, (0, 0, 0)))
        self.assertEqual(observed, [124])
        self.assertEqual(
            [(e.reference, e.level) for e in preview.actors[7].state_ledger.entries],
            [(3617, 124)],
        )
        self.assertTrue(packets)
