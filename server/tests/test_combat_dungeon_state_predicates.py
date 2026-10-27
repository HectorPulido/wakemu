"""Original world facts and authenticated existing state-query relationships."""

from copy import deepcopy
from dataclasses import asdict, replace
import os
from unittest.mock import patch

from postgres_case import PostgresCase


class DungeonStatePredicateComponentTests(PostgresCase):
    @classmethod
    def setUpClass(cls):
        if not os.environ.get("WAKFU_RIFT_CARRIER_DATASET"):
            return
        from test_rift_native_carrier_component import NativeRiftCarrierComponentTests

        NativeRiftCarrierComponentTests.setUpClass()
        cls.carrier = NativeRiftCarrierComponentTests()

    def test_original_sql_world_flags_and_authenticated_state_getter(self):
        if not hasattr(self, "carrier"):
            self.skipTest("Explicit bounded native projection required")
        from wakfu_server import native_world_dungeon_facts as worlds
        from wakfu_server.combat_conditions import (
            ConditionActor,
            ConditionContext,
            UnknownCondition,
            evaluate_condition,
        )
        from wakfu_server.combat_effect_dispatch import EffectInvocation
        from wakfu_server.rift_native_gameplay import apply_native_carrier
        from wakfu_server.combat_event_replay import NativeEventSource
        from wakfu_server.fight_checkpoint_store import snapshot

        worlds.dungeon_world_flags.cache_clear()
        self.addCleanup(worlds.dungeon_world_flags.cache_clear)
        with patch.object(worlds, "_database", return_value=self.store) as database:
            flags = worlds.dungeon_world_flags()
            self.assertEqual((len(flags), sum(flags.values())), (720, 169))
            self.assertFalse(worlds.is_dungeon(1134))
            self.assertTrue(worlds.is_dungeon(1159))
            # Original eyd flags, independent of the synthetic Rift mode.
            self.assertTrue(worlds.is_dungeon(1318))
            self.assertTrue(worlds.is_dungeon(1329))
            self.assertEqual(database.call_count, 1)
            with self.assertRaises(ValueError):
                worlds.is_dungeon(999999999)
            for invalid in (None, True, "1159"):
                with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                    worlds.is_dungeon(invalid)
            with self.assertRaises(TypeError):
                flags[1134] = True
            for identity, expected in ((1134, False), (1159, True)):
                component = self.carrier.fixture(
                    1, controller_registration=True, native_map_id=identity
                )
                dispatcher, _ = component.factory(component.fight)
                invocation = EffectInvocation(
                    315255, 1, 7, 7, component.fight.actors[7].position
                )
                context = dispatcher.condition_context(invocation)
                before = snapshot(component.fight)
                self.assertIs(evaluate_condition("IsDungeon()", context), expected)
                self.assertTrue(
                    evaluate_condition(
                        "IsDungeon() == " + ("0" if expected else "-1"), context
                    )
                )
                self.assertIs(
                    evaluate_condition("IsDungeon(123)", context), expected
                )  # eNL ignores arguments.
                self.assertEqual(snapshot(component.fight), before)
                self.assertEqual(database.call_count, 1)
            for context in (
                ConditionContext({}),
                ConditionContext({}, dungeon_query=lambda: 0),
            ):
                with self.assertRaises(UnknownCondition):
                    evaluate_condition("IsDungeon()", context)
            # The shared retained state producer applies the actual source graph.
            component = self.carrier.fixture(1, controller_registration=True)
            fight = component.fight
            dispatcher, _ = component.factory(fight)
            lifecycle = dispatcher.native_retention.stat_handler.event_lifecycle
            original_replay = lifecycle.replay
            captured = []

            def observe(event, **kwargs):
                captured.append(event)
                return original_replay(event, **kwargs)

            with patch.object(lifecycle, "replay", observe), fight.effect_resolution():
                apply_native_carrier(dispatcher, actor_id=7, reference=6808, grade=4)
            source = next(
                event
                for event in captured
                if isinstance(event, NativeEventSource)
                and event.generic_effect == 315255
                and event.channel == 3
                and event.target_id == 7
            )
            source.validate()
            with self.assertRaises(ValueError):
                replace(source, native_events_verified=False).validate()
            source_context = asdict(
                replace(source, final_modifier=None, runner_modifier=None)
            )
            source_context.pop("final_modifier", None)
            source_context.pop("runner_modifier", None)
            listener = EffectInvocation(
                315255,
                1,
                -200,
                -201,
                fight.actors[-201].position,
                native_trigger_context=source_context,
            )
            context = dispatcher.condition_context(listener)
            before = snapshot(fight)
            self.assertTrue(
                evaluate_condition(
                    'GetStateLevel(6808,"triggeringTarget") == 4', context
                )
            )
            self.assertTrue(
                evaluate_condition('GetStateLevel(6808,"target") == -1', context)
            )
            self.assertTrue(
                evaluate_condition(
                    'GetStateLevel(1896,"triggeringTarget") == -1', context
                )
            )
            empty = dispatcher.condition_context(
                replace(listener, native_trigger_context=None)
            )
            self.assertTrue(
                evaluate_condition(
                    'GetStateLevel(6808,"triggeringTarget") == -1', empty
                )
            )
            missing = deepcopy(source_context)
            missing.pop("target_id")
            with self.assertRaises(ValueError):
                malformed = dispatcher.condition_context(
                    replace(listener, native_trigger_context=missing)
                )
                evaluate_condition(
                    'GetStateLevel(6808,"triggeringTarget") == 4', malformed
                )
            foreign = deepcopy(source_context)
            foreign["target_id"] = 999999999
            with self.assertRaises(ValueError):
                dispatcher.condition_context(
                    replace(listener, native_trigger_context=foreign)
                )
            spoof = ConditionContext(
                {"triggeringtarget": ConditionActor(state_levels=((6808, 99),))}
            )
            with self.assertRaises(UnknownCondition):
                evaluate_condition(
                    'GetStateLevel(6808,"triggeringTarget") == 99', spoof
                )
            for invalid in (
                'GetStateLevel(1896,"all") == 0',
                'GetStateLevel(true,"triggeringTarget") == 0',
            ):
                with self.assertRaises(UnknownCondition):
                    evaluate_condition(invalid, context)
            self.assertEqual(snapshot(fight), before)
