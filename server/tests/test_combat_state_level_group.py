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

    def test_null_target_rebind_keeps_actual_caster_before_state_lookup(self):
        from dataclasses import replace

        invocation = replace(self.inv, target_id=None)
        self.actors[7].state_ledger.entries = [SimpleNamespace(reference=12, level=17)]
        for rebind in (1, 2):
            effect, values = self.effect([0, 0, 0, 0, 1, rebind, 12, 1])
            self.assertEqual(child_level(effect, values, invocation, self.actors), 17)

    def area_fixture(self, with_qf):
        from wakfu_server.combat_state_ledger import StateLedger, RunningState

        row = dict(
            uid=91,
            reference=111,
            cell=(2, 3, 0),
            native_area_contract="faY",
            native_running_effect_manager=with_qf,
        )
        if with_qf:
            ledger = StateLedger(91)
            ledger._entries = (
                RunningState(
                    301, 12, 17, 7, 91, -1, "target", False, (), 0, True, None
                ),
            )
            row["state_ledger"] = ledger
        fight = SimpleNamespace(actors=self.actors, native_effect_areas={91: row})
        definitions = {
            "111": dict(
                type="GLYPH",
                native_area_properties=[12] if with_qf else [],
                entry_masks=[],
            )
        }
        return fight, definitions

    def test_runtime_registered_area_qf_supplies_first_matching_state(self):
        from dataclasses import replace
        from unittest.mock import patch
        from wakfu_server.combat_state_level_group import runtime_child_level

        fight, definitions = self.area_fixture(True)
        effect, values = self.effect([0, 0, 1, 0, 1, 0, 12])
        with patch(
            "wakfu_server.combat_effect_area.native_effect_areas",
            return_value=definitions,
        ):
            self.assertEqual(
                runtime_child_level(
                    effect, values, replace(self.inv, target_id=91), fight
                ),
                17,
            )
        self.assertNotIn(91, fight.actors)

    def test_null_pv_and_registered_null_qf_have_distinct_constant_contracts(self):
        from dataclasses import replace
        from unittest.mock import patch
        from wakfu_server.combat_state_level_group import runtime_child_level

        fight, definitions = self.area_fixture(False)
        effect, values = self.effect([0, 0, 1, 0, 1, 0, 12, 0, 1, 3])
        with patch(
            "wakfu_server.combat_effect_area.native_effect_areas",
            return_value=definitions,
        ):
            self.assertEqual(
                runtime_child_level(
                    effect, values, replace(self.inv, target_id=91), fight
                ),
                3,
            )
            self.assertEqual(
                runtime_child_level(
                    effect, values, replace(self.inv, target_id=None), fight
                ),
                30,
            )
            self.assertEqual(
                runtime_child_level(
                    effect,
                    values,
                    replace(self.inv, target_id=None),
                    fight,
                    return_native_override=True,
                ),
                -1,
            )
        self.assertNotIn("state_ledger", fight.native_effect_areas[91])

    def test_unknown_nonnull_pv_cannot_be_treated_as_native_null(self):
        from dataclasses import replace
        from wakfu_server.combat_state_level_group import runtime_child_level

        effect, values = self.effect([0, 0, 1, 0, 1, 0, 12, 0, 1, 3])
        with self.assertRaisesRegex(ValueError, "level-source PV"):
            runtime_child_level(
                effect,
                values,
                replace(self.inv, target_id=99),
                SimpleNamespace(actors=self.actors),
            )

    def test_retained_wire_and_child_evaluation_use_actual_area_override(self):
        from dataclasses import replace
        from unittest.mock import patch
        from wakfu_server.combat_retained_runtime import NativeRetainedRuntime
        from wakfu_server.combat_effect_removal import _identity_fields

        runtime = object.__new__(NativeRetainedRuntime)
        runtime.fight, definitions = self.area_fixture(True)
        runtime.plan = {
            "native_retained_container": {"present": True, "type": 11, "level": 23}
        }
        effect, values = self.effect([0, 0, 1, 0, 1, 0, 12])
        effect["native_effect_flags"] = [16]
        with patch(
            "wakfu_server.combat_effect_area.native_effect_areas",
            return_value=definitions,
        ):
            level, wire = runtime.child_level_context(
                effect, values, replace(self.inv, target_id=91), default_level=30
            )
        self.assertEqual(level, 17)
        self.assertEqual(_identity_fields(wire, integer_fields=(4,))[4], 17)
