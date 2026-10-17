"""Current vitality execution verified by independent native behavior contracts."""
from copy import deepcopy
import unittest
from unittest.mock import patch

import test_combat_damage_handler as damage_cases
import test_combat_healing_handler as healing_cases
import test_combat_retained_damage as retained_cases
import test_combat_actor_snapshot as snapshot_cases
import test_combat_copied_pa as copied_cases
import test_combat_wall_area as wall_cases
from wakfu_server.combat_geometry_snapshot import source_snapshot
from wakfu_server.combat_effect_removal import _identity_fields


class VitalityMigrationTests(unittest.TestCase):
    def _run(self, suite, method):
        fixture = suite(methodName=method)
        fixture.setUp()
        try:
            getattr(fixture, method)()
        finally:
            fixture.doCleanups()

    def _assert_native_suite(self, suite):
        names = unittest.defaultTestLoader.getTestCaseNames(suite)
        self.assertTrue(names)
        for method in names:
            with self.subTest(case=method):
                self._run(suite, method)

    def test_damage_contracts_preserve_complete_state_events_and_wire(self):
        self._assert_native_suite(damage_cases.DamageHandlerTests)

    def test_healing_contracts_preserve_complete_state_events_and_wire(self):
        self._assert_native_suite(healing_cases.HealingHandlerTests)

    def test_retained_damage_preserves_ownership_expiration_and_wire(self):
        self._assert_native_suite(retained_cases.RetainedDamageTests)

    def test_damage_and_healing_use_shared_plan_and_mutation_once(self):
        from wakfu_server import combat_damage_handler, combat_healing_handler

        for suite, module, plan, apply in (
            (
                damage_cases.DamageHandlerTests,
                combat_damage_handler,
                "plan_damage_consumption",
                "apply_damage_consumption",
            ),
            (
                healing_cases.HealingHandlerTests,
                combat_healing_handler,
                "plan_healing_consumption",
                "apply_healing_consumption",
            ),
        ):
            with self.subTest(family=suite.__name__):
                fixture = suite()
                fixture.setUp()
                self.addCleanup(fixture.doCleanups)
                with patch.object(
                    module, plan, wraps=getattr(module, plan)
                ) as planner, patch.object(
                    module, apply, wraps=getattr(module, apply)
                ) as mutation:
                    self.assertTrue(
                        fixture.handler(fixture.effect, {}, fixture.invocation)
                    )
                self.assertEqual(planner.call_count, 1)
                self.assertEqual(mutation.call_count, 1)

    def test_rejected_native_context_preserves_state_and_delivery(self):
        from dataclasses import replace

        for suite in (
            damage_cases.DamageHandlerTests,
            healing_cases.HealingHandlerTests,
        ):
            with self.subTest(family=suite.__name__):
                fixture = suite()
                fixture.setUp()
                self.addCleanup(fixture.doCleanups)
                context = replace(
                    fixture.handler.context(fixture.effect, fixture.invocation),
                    executable=False,
                )
                fixture.handler.context = lambda *unused: context
                before = deepcopy(source_snapshot(fixture.fight))
                self.assertFalse(
                    fixture.handler(fixture.effect, {}, fixture.invocation)
                )
                self.assertEqual(source_snapshot(fixture.fight), before)
                self.assertEqual(fixture.packets, [])

    def test_native_fresh_raw_hp_damage_preserves_hidden_constructor_operand(self):
        from wakfu_server.combat_actor_snapshot import build_player_snapshot
        from wakfu_server.combat_hp_raw import hp_raw_current, set_hp_raw_maximum

        fixture = damage_cases.DamageHandlerTests()
        fixture.setUp()
        character, target = snapshot_cases.ActorSnapshotTests().player()
        character["id"], target.id = -7, -7
        target.team, target.position = 1, fixture.fight.actors[-7].position
        snapshot = build_player_snapshot(
            character, target, wp_current=6, wp_maximum=6, running_effects=()
        )
        snapshot.install(target)
        set_hp_raw_maximum(target, 20)
        fixture.fight.actors[-7] = target
        fixture.fight.actors[7].effect_stats[100] = 0
        fixture.effect["parameters"] = [10, 0]
        self.assertEqual((target.hp, hp_raw_current(target)), (20, 41))
        self.assertTrue(fixture.handler(fixture.effect, {}, fixture.invocation))
        self.assertEqual((target.hp, hp_raw_current(target)), (20, 31))
        self.assertEqual(target.native_hp_on_operand["raw_current"], 41)
        self.assertEqual([opcode for opcode, _ in fixture.packets], [12613])
        self.assertEqual(_identity_fields(fixture.packets[0][1][19:])[4], 10)

    def test_copied_pa_damage_then_heal_preserves_signed_raw_and_virtual_delta(self):
        from wakfu_server.combat_character_copy_metadata import (
            native_copy_characteristics,
        )
        from wakfu_server.combat_copied_pa import (
            install_copied_pa_pool,
            copied_raw_current,
            set_copied_maximum,
        )
        from wakfu_server.combat_healing_handler import NativeHealingHandler

        fixture = damage_cases.DamageHandlerTests()
        fixture.setUp()
        fight = fixture.fight
        target = fight.actors[-7]
        _, _, rows, source = copied_cases.CopiedPATests().fixture()
        install_copied_pa_pool(
            target,
            rows,
            metadata=native_copy_characteristics(),
            source_record={**source, "actor_id": target.id},
        )
        set_copied_maximum(fight, target, 92, 200)
        fixture.fight.actors[7].effect_stats[100] = 0
        fixture.effect["parameters"] = [10, 0]
        self.assertTrue(fixture.handler(fixture.effect, {}, fixture.invocation))
        self.assertEqual((target.hp, copied_raw_current(target, 1)), (82, 115))
        healing_fixture = healing_cases.HealingHandlerTests()
        healing_fixture.setUp()
        healer = NativeHealingHandler(
            fight,
            fixture.packets,
            action_id=2,
            allocate_uid=lambda: 100,
            context=lambda *args: healing_fixture.context,
            rng=lambda: 0.99,
        )
        self.assertTrue(
            healer(
                {"effect_class": 25, "parameters": [1, 0], "native_effect_flags": []},
                {},
                fixture.invocation,
            )
        )
        # HP.on collapses raw115 to82 (actual-33); native overflow uses
        # remaining34, so actual serialized restoration is still1.
        self.assertEqual((target.hp, copied_raw_current(target, 1)), (82, 82))
        self.assertEqual(
            (target.effect_stats[92], copied_raw_current(target, 92)), (34, 34)
        )
        self.assertEqual([opcode for opcode, _ in fixture.packets], [12613, 12613])
        self.assertEqual(
            [_identity_fields(payload[19:])[4] for _, payload in fixture.packets],
            [10, 1],
        )

    def test_native_wall_hp_and_qi_lifecycle_preserves_native_contract(self):
        from wakfu_server.combat_damage_handler import NativeDamageHandler

        original = NativeDamageHandler.__call__
        observed = []

        def capture(handler, *args, **kwargs):
            outcome = original(handler, *args, **kwargs)
            observed.append(
                (
                    outcome,
                    deepcopy(source_snapshot(handler.fight)),
                    deepcopy(handler.packets),
                )
            )
            return outcome

        method = "test_damage_updates_wall_pa_without_actor_alias_or_hp0_qi_removal"
        fixture = wall_cases.NativeWallConstructorTests(methodName=method)
        with patch.object(NativeDamageHandler, "__call__", capture):
            getattr(fixture, method)()
        self.assertEqual(len(observed), 2)

    def test_live_l2_absorption_freezing_and_death_handoff_keep_native_order(self):
        for scenario in ("live_absorption", "frozen_absorption", "death"):
            fixture = damage_cases.DamageHandlerTests()
            fixture.setUp()
            fight = fixture.fight
            source, target = fight.actors[7], fight.actors[-7]
            order = []
            if scenario == "frozen_absorption":
                source.effect_frozen = frozenset({100})
                target.effect_frozen = frozenset({97})
            if scenario == "death":
                target.hp = 20

            class Events:
                def phase(_, effect, invocation, **data):
                    order.append(("phase", data["channel"], target.hp))
                    if data["channel"] == 2 and scenario == "live_absorption":
                        source.effect_stats[100] = 2
                        target.effect_stats[97] = 7

                def death(_, actor_id, **data):
                    order.append(("death", actor_id, target.hp))

            fixture.handler.event_lifecycle = Events()
            self.assertTrue(fixture.handler(fixture.effect, {}, fixture.invocation))
            if scenario == "live_absorption":
                self.assertEqual(target.hp, 38)
                self.assertEqual(source.effect_stats[100], 0)
                self.assertEqual(target.effect_stats[97], 0)
            elif scenario == "frozen_absorption":
                self.assertEqual(target.hp, 29)
                self.assertEqual(source.effect_stats[100], 15)
                self.assertEqual(target.effect_stats[97], 20)
            else:
                self.assertEqual(target.hp, 0)
                self.assertEqual(
                    order,
                    [
                        ("phase", 2, 20),
                        ("death", -7, 0),
                        ("phase", 3, 0),
                        ("phase", 4, 0),
                    ],
                )
            self.assertEqual(len(fixture.packets), 1)


if __name__ == "__main__":
    unittest.main()
