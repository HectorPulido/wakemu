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

    def test_life_steal_marker_is_family_scoped_and_preserves_native_healing(self):
        """eVl29 marks eXv HP gain; it introduces no arithmetic branch."""
        from dataclasses import replace
        from test_combat_equipment_operation_capability import (
            CombatEquipmentOperationCapabilityTests,
        )
        from wakfu_server.combat_value_transfer import transfer_value_context

        _, (
            _,
            provider,
        ) = CombatEquipmentOperationCapabilityTests()._factory_capability()
        for family, flags, expected in (
            (24, (), True),
            (24, (29,), True),
            (25, (29,), False),
            (24, (999,), False),
        ):
            with self.subTest(family=family, flags=flags):
                effect = dict(_effect(family, (0, 1)), native_effect_flags=flags)
                self.assertIs(
                    provider(
                        kind="context",
                        effect=effect,
                        level=32767,
                        operation_id="healing.apply",
                        requires_context=("native_healing_execution",),
                        detail="native_healing_execution",
                    ),
                    expected,
                )

        results = []
        for flags in ((), (29,)):
            fixture = healing_fixture.HealingHandlerTests()
            fixture.setUp()
            fixture.fight.actors[7].effect_stats[53] = 50
            fixture.fight.actors[-7].effect_stats[32] = 200
            invocation = replace(
                fixture.invocation,
                reference=381691,
                level=32767,
                native_context_hex=transfer_value_context(b"", 10).hex(),
            )
            effect = dict(effect_class=24, parameters=[0, 1], native_effect_flags=flags)
            self.assertTrue(fixture.handler(effect, {}, invocation))
            target = fixture.fight.actors[-7]
            results.append((target.hp, deepcopy(target.effect_stats), fixture.packets))
            for invalid in (
                dict(effect, effect_class=25, native_effect_flags=(29,)),
                dict(effect, native_effect_flags=(999,)),
            ):
                before = (
                    target.hp,
                    deepcopy(target.effect_stats),
                    list(fixture.packets),
                )
                with self.assertRaisesRegex(
                    ValueError, "Unhandled native healing flags"
                ):
                    fixture.handler(invalid, {}, invocation)
                self.assertEqual(
                    before, (target.hp, target.effect_stats, fixture.packets)
                )
        self.assertEqual(results[0], results[1])
        self.assertEqual((100, 7), (results[1][0], results[1][1][92]))

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
            subscription=False,
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
        # A retained non-subscribed runner needs cvX/eIK=false; cvY would
        # discard it at the original aTR manager admission guard.
        self.assertEqual([12613, 13560], [opcode for opcode, _ in packets])

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

    def test_original_leaves_use_native_resolver_timing_retention_and_level_windows(
        self,
    ):
        """Original five descriptors traverse the shared dispatch consumers.

        This is a bounded operator component, not a paid scroll/build fight or
        an assertion that the parent listeners' event eligibility was earned.
        """
        import json
        from pathlib import Path
        from wakfu_server.combat_conditions import ConditionActor, ConditionContext
        from wakfu_server.combat_effect_dispatch import EffectDispatcher
        from wakfu_server.combat_effect_resolver import (
            NativeEffectResolver,
            EffectResolutionContext,
        )
        from wakfu_server.combat_native_timing_context import NativeEffectTimingProvider

        data = json.loads(
            (
                Path(__file__).parent
                / "fixtures"
                / "native_sublimation_residual_leaves.json"
            ).read_text()
        )
        effects = data["effects"]
        fixture = healing_fixture.HealingHandlerTests()
        fixture.setUp()
        fight = fixture.fight
        fight.native_effect_uid_next = 902
        for member in fight.actors.values():
            member.effect_stats[1] = member.hp
            member.effect_maxima[1] = member.max_hp
            member.effect_minima = {stat: 0 for stat in member.effect_stats}
            member.effect_base_minima = dict(member.effect_minima)
            member.effect_base_maxima = dict(member.effect_maxima)
            member.effect_percentages = {stat: 0 for stat in member.effect_stats}
        actor = fight.actors[7]
        actor.hp = 60
        actor.effect_stats[1] = 60
        actor.effect_maxima[1] = actor.max_hp
        actor.effect_minima[1] = 0
        packets = []
        timing = NativeEffectTimingProvider({"states": {}, "effects": effects})
        plan = {"native_retained_container": {"present": False}}
        retention = NativeRetainedRuntime(
            fight,
            packets,
            plan=plan,
            state_catalog={"states": {}, "effects": effects},
            action_id=1,
            timing=timing,
            metadata=data["retained_metadata"],
        )
        healing = healing_fixture.NativeHealingHandler(
            fight,
            packets,
            action_id=1,
            allocate_uid=fight.allocate_effect_uid,
            context=lambda *_: fixture.context,
            rng=lambda: 0.99,
        )
        final = NativeFinalModifierHandler(
            fight,
            packets,
            action_id=1,
            allocate_uid=fight.allocate_effect_uid,
            context=lambda effect, invocation: timing.stat(
                fight, plan, effect, invocation
            ),
        )
        native_context = {
            identity: dict(
                bEe=True,
                is_amO=True,
                is_eGj=True,
                is_Qq=False,
                is_eHH=True,
                UNTARGETTABLE_BY_OTHER=False,
                buX=False,
            )
            for identity in fight.actors
        }
        resolver = NativeEffectResolver(
            actors=lambda *_: tuple(fight.actors.values()),
            caster=lambda _effect, invocation: fight.actors[invocation.caster_id],
            native_context=lambda *_: native_context,
            context=lambda *_: EffectResolutionContext(
                "EFFECTS_ONLY", "immediate", "actors", True
            ),
        )

        def conditions(invocation):
            def actual(identity):
                member = fight.actors[identity]
                return ConditionActor(
                    actor_id=identity,
                    effective_level=member.effective_level,
                    state_ids=frozenset(
                        row.reference for row in member.state_ledger.entries
                    ),
                    state_levels=tuple(
                        (row.reference, row.level)
                        for row in member.state_ledger.entries
                    ),
                )

            return ConditionContext(
                {
                    "caster": actual(invocation.caster_id),
                    "target": actual(invocation.target_id),
                }
            )

        dispatcher = EffectDispatcher(
            effects,
            {25: retention.wrap(healing), 1093: retention.wrap(final)},
            resolve=resolver,
            condition_context=conditions,
            probability_accepts=lambda probability, _: probability == 100,
            group_cells=lambda *_: (),
            actor_position=lambda identity: fight.actors[identity].position,
        )
        heal = effects["315544"]
        self.assertEqual(heal["native_effect_flags"], [3])
        self.assertTrue(
            dispatcher.execute(EffectInvocation(315544, 2, 7, 7, actor.position))
        )
        self.assertGreater(actor.hp, 60)
        self.assertEqual(set(fight.actors), {7, -7})
        self.assertFalse(fight.owned_stat_effects)  # Original heal duration is zero.

        modifier = NativeFinalModifier(901, 1)
        before = {
            identity: deepcopy(member.effect_stats)
            for identity, member in fight.actors.items()
        }
        with final_modifier_source(source(modifier)):
            self.assertTrue(
                dispatcher.execute(
                    EffectInvocation(
                        283250,
                        2,
                        7,
                        7,
                        actor.position,
                        native_trigger_context={"uid": 901},
                    )
                )
            )
        self.assertEqual(modifier.value, -15)
        (uid,) = fight.owned_stat_effects
        self.assertEqual(fight.native_retained_records[uid]["effect_class"], 1093)
        remover = NativeStatHandler(
            fight,
            packets,
            {"effects": {}},
            action_id=1,
            allocate_uid=fight.allocate_effect_uid,
            context=lambda *_: None,
        )
        remover.remove(uid)
        retention.synchronize()
        self.assertEqual(modifier.value, -15)
        self.assertNotIn(uid, fight.native_retained_records)
        self.assertEqual(
            before,
            {
                identity: member.effect_stats
                for identity, member in fight.actors.items()
            },
        )
        # Native direct_healing is cvX12613; retained eZJ also needs the
        # evaluated cvX path because its original masks are not subscribed.
        self.assertEqual([12613, 12613, 13560], [opcode for opcode, _ in packets])

        boundary = (
            fight.native_effect_uid_next,
            deepcopy(fight.owned_stat_effects),
            tuple(packets),
        )
        for reference in (407838, 407841, 407848):
            self.assertFalse(
                dispatcher.execute(EffectInvocation(reference, 0, 7, 7, actor.position))
            )
        self.assertEqual(
            boundary,
            (fight.native_effect_uid_next, fight.owned_stat_effects, tuple(packets)),
        )
