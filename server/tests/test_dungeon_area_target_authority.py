"""Native area targets keep non-summon identity and absent wall resources."""
from copy import deepcopy
import unittest

import test_combat_fake_fighter_area as area_fixture
from wakfu_server.combat_conditions import UnknownCondition, evaluate_condition
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_maximum_resource import (
    NativeMaximumReductionHandler,
    _reduction_area_lacks_characteristic,
    remove_maximum_reduction,
)
from wakfu_server.combat_stat_handler import StatExecutionContext
from wakfu_server.combat_state_timing import StateTimer


class DungeonWallResourceAuthorityTests(unittest.TestCase):
    @staticmethod
    def area_snapshot(row):
        ledger = row.get("state_ledger")
        return (
            deepcopy(
                {key: value for key, value in row.items() if key != "state_ledger"}
            ),
            None if ledger is None else (ledger.actor_id, tuple(ledger.entries)),
        )

    def create(self):
        (
            fight,
            creator,
            allocated,
            packets,
        ) = area_fixture.NativeFakeFighterAreaTests().create()
        self.assertTrue(
            creator(
                {"effect_class": 339},
                {"parameters": [196, 74]},
                EffectInvocation(412354, 74, 7, None, (2, 3, 0)),
            )
        )
        fight.phase = "active"
        fight.owned_stat_effects = {}
        packets.clear()
        handler = NativeMaximumReductionHandler(
            fight,
            packets,
            action_id=2,
            allocate_uid=creator.allocate_uid,
            context=lambda *args: StatExecutionContext(
                True, True, None, True, b"", StateTimer(7, 2, "end")
            ),
        )
        return fight, handler, allocated, packets

    def test_real_wall_absent_ap_mp_wp_retains_muted_runner_and_removes_without_pa(
        self,
    ):
        for family in (56, 57, 192):
            with self.subTest(family=family):
                fight, handler, _, packets = self.create()
                row = fight.native_effect_areas[901]
                before = self.area_snapshot(row)
                self.assertTrue(
                    handler(
                        {"effect_class": family, "parameters": [2.0, 0.0]},
                        {},
                        EffectInvocation(326073, 37, 7, 901, (2, 3, 0)),
                    )
                )
                self.assertEqual(self.area_snapshot(row), before)
                self.assertNotIn(901, fight.actors)
                self.assertEqual(packets, [])
                uid, entry = next(iter(fight.owned_stat_effects.items()))
                self.assertTrue(entry["native_absent_characteristic"])
                self.assertEqual(entry["actual"], 2)
                remove_maximum_reduction(handler, uid)
                self.assertEqual(self.area_snapshot(row), before)
                self.assertEqual(fight.owned_stat_effects, {})
                self.assertEqual([opcode for opcode, _ in packets], [13560])

    def test_corrupt_wall_constructor_and_unknown_pv_still_reject_before_uid_or_packet(
        self,
    ):
        fight, handler, allocated, packets = self.create()
        before = list(allocated)
        effect = {"effect_class": 56, "parameters": [2.0, 0.0]}
        with self.assertRaisesRegex(ValueError, "target PV"):
            handler(effect, {}, EffectInvocation(326073, 37, 7, 999, (2, 3, 0)))
        fight.native_effect_areas[901]["native_wall_constructor"]["hp_maximum"] += 1
        with self.assertRaises(ValueError):
            handler(effect, {}, EffectInvocation(326073, 37, 7, 901, (2, 3, 0)))
        self.assertEqual(allocated, before)
        self.assertEqual((fight.owned_stat_effects, packets), ({}, []))

    def test_wall_hp_is_never_certified_as_absent_resource(self):
        fight, _, _, packets = self.create()
        with self.assertRaisesRegex(ValueError, "Unproven native wall"):
            _reduction_area_lacks_characteristic(fight, 901, 1)
        self.assertEqual(packets, [])


class DungeonAreaSummonIdentityTests(unittest.TestCase):
    def fixture(self):
        from wakfu_server.combat_runtime_adapter import (
            NativeCastAuthority,
            NativeServerRuntimeAdapter,
        )

        fight, _, _, _ = DungeonWallResourceAuthorityTests().create()
        fight.current = None
        # This identity-only fixture does not attest the complete retained
        # effect population. dTE is independent of optional Qf query metadata.
        fight.native_retained_tracking = False

        def unused(*args, **kwargs):
            raise AssertionError("Area identity query must not execute a cast policy")

        cast = NativeCastAuthority(
            unused,
            unused,
            unused,
            unused,
            unused,
            unused,
            unused,
            lambda *args: None,
            unused,
            unused,
        )
        adapter = NativeServerRuntimeAdapter(actor_authority=unused, cast=cast)
        return fight, adapter

    def test_actual_registered_wall_and_retained_pointer_are_not_summons(self):
        from wakfu_server.combat_effect_area import remove_owned_hour_area
        from wakfu_server.combat_state_managers import selected_area_pv_scope

        fight, adapter = self.fixture()
        # Both selectors deliberately name an actual area PV. No ordinary
        # actor snapshot or compiled spell fixture supplies their identity.
        invocation = EffectInvocation(326115, 74, 901, 901, None)
        context = adapter.condition(fight, {}, None, invocation)
        self.assertFalse(evaluate_condition('IsSummon("target")', context))
        self.assertFalse(evaluate_condition('IsSummon("caster")', context))
        self.assertFalse(context.actors["target"].is_native_fighter)
        with selected_area_pv_scope(fight, (901,)):
            remove_owned_hour_area(fight, 901)
            retained = adapter.condition(fight, {}, None, invocation)
            self.assertFalse(evaluate_condition('IsSummon("target")', retained))
        with self.assertRaisesRegex(ValueError, "Unregistered"):
            adapter.condition(fight, {}, None, invocation)

    def test_missing_fighter_summon_authority_remains_unknown(self):
        from wakfu_server.combat_conditions import ConditionActor, ConditionContext

        context = ConditionContext({"target": ConditionActor(actor_id=7)})
        with self.assertRaisesRegex(UnknownCondition, "dTE"):
            evaluate_condition('IsSummon("target")', context)
        summoned = ConditionContext(
            {"target": ConditionActor(actor_id=7, is_summon=True)}
        )
        self.assertTrue(evaluate_condition('IsSummon("target")', summoned))
