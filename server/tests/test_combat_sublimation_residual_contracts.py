"""Shared healing, triggering modifier and native level-window regressions."""
from copy import deepcopy
from types import SimpleNamespace
import unittest

from test_combat_equipment_operation_capability import (
    _effect,
    _provider,
    _runtime_binding,
)
import test_combat_healing_handler as healing_fixture
from test_combat_final_modifier import source
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_equipment_operation_capability import validate_graph
from wakfu_server.combat_final_modifier import (
    NativeFinalModifier,
    NativeFinalModifierHandler,
    final_modifier_source,
)
from wakfu_server.combat_retained_runtime import NativeRetainedRuntime
from wakfu_server.combat_stat_handler import NativeStatHandler, StatExecutionContext


class SublimationResidualContractsTests(unittest.TestCase):
    def test_healing_hidden_zone_is_presentational_and_unknown_flags_reject(self):
        baseline, hidden = (
            healing_fixture.HealingHandlerTests(),
            healing_fixture.HealingHandlerTests(),
        )
        baseline.setUp()
        hidden.setUp()
        hidden.effect["native_effect_flags"] = [3]
        self.assertTrue(baseline.handler(baseline.effect, {}, baseline.invocation))
        self.assertTrue(hidden.handler(hidden.effect, {}, hidden.invocation))
        self.assertEqual(baseline.fight.actors[-7].hp, hidden.fight.actors[-7].hp)
        self.assertEqual(baseline.packets, hidden.packets)
        before = deepcopy(hidden.fight.actors[-7].effect_stats)
        with self.assertRaisesRegex(ValueError, "Unhandled native healing flags"):
            hidden.handler(
                dict(hidden.effect, native_effect_flags=[999]), {}, hidden.invocation
            )
        self.assertEqual(before, hidden.fight.actors[-7].effect_stats)

    def test_retained_final_modifier_has_central_ownership_and_no_stat_inverse(self):
        fixture = healing_fixture.HealingHandlerTests()
        fixture.setUp()
        fight, packets = fixture.fight, []
        before = {
            key: deepcopy(actor.effect_stats) for key, actor in fight.actors.items()
        }
        effect = _effect(1093, (0, -7.5))
        metadata = dict(
            effect_class=1093,
            variant=0,
            minimum_level=0,
            maximum_level=32767,
            parameters=[0, -7.5],
            definition_type=0,
            definition_dispellable=None,
            owner_on_caster=False,
        )
        retention = NativeRetainedRuntime(
            fight,
            packets,
            plan={"native_retained_container": {"present": False}},
            state_catalog={"states": {}, "effects": {}},
            action_id=1,
            timing=None,
            metadata={"effects": {"283250": metadata}},
        )
        handler = NativeFinalModifierHandler(
            fight,
            packets,
            action_id=1,
            allocate_uid=lambda: 902,
            context=lambda *_: StatExecutionContext(True, True, None, True, b"", None),
        )
        invocation = EffectInvocation(
            283250, 2, 7, -7, (1, 0, 0), native_trigger_context={"uid": 901}
        )
        modifier = NativeFinalModifier(901, 1)
        with final_modifier_source(source(modifier)):
            self.assertTrue(retention.wrap(handler)(effect, {}, invocation))
        self.assertEqual(-15, modifier.value)
        self.assertEqual(1093, fight.native_retained_records[902]["effect_class"])
        stat = NativeStatHandler(
            fight,
            packets,
            {"effects": {}},
            action_id=1,
            allocate_uid=lambda: 903,
            context=lambda *_: None,
        )
        stat.remove(902)
        retention.synchronize()
        self.assertEqual(-15, modifier.value)  # No inverse on an ended source Qe.
        self.assertNotIn(902, fight.native_retained_records)
        self.assertEqual(
            before, {key: actor.effect_stats for key, actor in fight.actors.items()}
        )
        self.assertEqual([13497, 13560], [opcode for opcode, _ in packets])

    def test_native_child_level_windows_skip_execution_without_skipping_metadata(self):
        root = _effect(330, ())
        root["children"] = (2,)
        child = _effect(330, ())
        child.update(minimum_level=1, maximum_level=2, children=(3,))
        compiled = SimpleNamespace(
            effects={"1": root, "2": child}, source_states={"states": {}, "effects": {}}
        )
        source_plan = dict(
            roots=(1,),
            unplanned_passive_effect_ids=(),
            attachment_field=24,
            native_retained_container={"level": 0},
        )

        def assess():
            return validate_graph(
                source_plan,
                compiled,
                {},
                runtime_bindings={330: _runtime_binding(330)},
                criteria_capability=_provider,
            )

        self.assertEqual("supported", assess().status)
        source_plan["native_retained_container"]["level"] = 1
        self.assertEqual("unknown", assess().status)  # Missing child3 is now reachable.
        source_plan["native_retained_container"]["level"] = 0
        child["parameter_count"] = 1
        self.assertEqual("unknown", assess().status)
        self.assertIn("malformed native operation metadata", assess().reasons)
