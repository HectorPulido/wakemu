"""Native Xelor dial-to-hour travel through the real 12161 movement entry."""
import struct
import unittest
from unittest.mock import patch

import test_xelor_runtime_pipeline as helpers
from wakfu_server.combat_movement_runtime import apply_client
from wakfu_server.combat_runtime_messages import RuntimeMessages


class XelorDialHandMovementTests(unittest.TestCase):
    def test_single_point_12161_travels_between_owned_hours_for_native_wp_gain(self):
        helper = helpers.XelorRuntimePipelineTests()
        # Keep the native hostile far enough from the dial's landing cell that
        # this test isolates hour travel rather than hostile tackle costs.
        data = helper.fixture(level=200, actives=(754, 775), target_distance=5)
        dial = helper.dial(data)
        data = helper.adopt(data, dial.fight)
        fight = data[2]
        actor = fight.actors[7]
        self.assertEqual(actor.position, (-6, -7, -1))
        before_wp = actor.effect_stats[4]
        self.assertGreater(before_wp, 0)
        before_hour = helper.states(actor)[6759]
        before_mp = actor.mp
        hours = {
            tuple(row["cell"]): row
            for row in fight.native_effect_areas.values()
            if row.get("owner_id") == 7 and row.get("native_hour_contract") is True
        }
        self.assertEqual(len(hours), 12)
        destination = (-11, -8, -1)
        self.assertIn(destination, hours)
        self.assertNotIn(destination, {item.position for item in fight.actors.values()})

        from wakfu_server.combat_area_transaction import prepare_area_movement

        runtime = RuntimeMessages(fight, stats_serializer=lambda current: b"")

        def area_provider(current, *, actor_id, action_id, path, origin):
            return prepare_area_movement(
                data[0],
                {-7: data[1]},
                current,
                data[3],
                actor_id=actor_id,
                action_id=action_id,
                path=path,
                origin=origin,
                rng=data[4],
            )

        request = struct.pack(">q", 7) + struct.pack(">iih", *destination)
        before = helpers.snapshot(runtime.fight)
        areas_before = dict(
            (uid, dict(row)) for uid, row in fight.native_effect_areas.items()
        )
        rng_before = data[4].getstate()
        with self.assertRaisesRegex(ValueError, "payment and area callbacks"):
            apply_client(runtime, 3, request, lambda current: b"")
        self.assertEqual(helpers.snapshot(runtime.fight), before)
        self.assertEqual(fight.native_effect_areas, areas_before)
        self.assertEqual(data[4].getstate(), rng_before)
        with patch(
            "wakfu_server.combat_hour_travel.try_apply_hour_travel",
            return_value=None,
        ) as legacy_hour_handler:
            with self.assertRaisesRegex(ValueError, "native facing vector"):
                apply_client(
                    runtime,
                    3,
                    request,
                    lambda current: b"",
                    area_provider=area_provider,
                )
        self.assertEqual(legacy_hour_handler.call_count, 1)
        self.assertEqual(helpers.snapshot(runtime.fight), before)
        self.assertEqual(fight.native_effect_areas, areas_before)
        self.assertEqual(data[4].getstate(), rng_before)
        from wakfu_server.combat_effect_dispatch import EffectDispatcher
        from wakfu_server.combat_event_replay import NativeEventReplay

        execute_original = EffectDispatcher.execute

        def reject_paid_hour_callback(dispatcher, invocation, **kwargs):
            activation = dispatcher._active_activation
            if (
                invocation.reference == 314228
                and activation is not None
                and activation[0] is invocation
                and 2263 in activation[1].event_ids
            ):
                dispatcher.group_random()
                raise RuntimeError("test-only hour callback rejection")
            return execute_original(dispatcher, invocation, **kwargs)

        with patch.object(EffectDispatcher, "execute", reject_paid_hour_callback):
            with self.assertRaisesRegex(
                RuntimeError, "test-only hour callback rejection"
            ):
                apply_client(
                    runtime,
                    3,
                    request,
                    lambda current: b"",
                    area_provider=area_provider,
                )
        self.assertEqual(helpers.snapshot(runtime.fight), before)
        self.assertEqual(fight.native_effect_areas, areas_before)
        self.assertEqual(data[4].getstate(), rng_before)

        clock_trace = []
        paid_wp_sources = []
        execute = EffectDispatcher.execute
        replay = NativeEventReplay.__call__

        def observe(dispatcher, invocation, **kwargs):
            result = execute(dispatcher, invocation, **kwargs)
            if invocation.reference in (314228, 413004, 413005):
                current = dispatcher.native_retention.fight.actors[7]
                clock_trace.append(
                    (
                        invocation.reference,
                        result,
                        helper.states(current).get(6759),
                        current.effect_stats.get(55),
                        current.effect_stats.get(4),
                    )
                )
            return result

        def observe_source(replayer, source, *, authority):
            if 2263 in source.event_ids:
                paid_wp_sources.append(
                    (source.channel, source.event_ids, source.value, source.cost_source)
                )
            return replay(replayer, source, authority=authority)

        with patch.object(EffectDispatcher, "execute", observe), patch.object(
            NativeEventReplay, "__call__", observe_source
        ):
            packets, event = apply_client(
                runtime,
                3,
                request,
                lambda current: b"",
                area_provider=area_provider,
            )
        self.assertEqual(event["path"], [destination])
        self.assertEqual(runtime.fight.actors[7].position, destination)
        self.assertEqual(runtime.fight.actors[7].mp, before_mp)
        self.assertEqual(runtime.fight.actors[7].effect_stats[4], before_wp - 1)
        # 314228 may be re-registered while its child changes the hour state;
        # the authoritative one-shot is the paid WP source on channel3.
        self.assertEqual(
            len([row for row in paid_wp_sources if row[0] == 3]), 1, paid_wp_sources
        )
        self.assertTrue(
            all(row[1] == (0, 60, 2263) for row in paid_wp_sources), paid_wp_sources
        )
        self.assertTrue(
            all(
                row[3]["movement_payment_policy"].get("payment_phase") == "hour_wp"
                for row in paid_wp_sources
            ),
            paid_wp_sources,
        )
        self.assertEqual(
            sum(row[0] == 413004 and row[1] is True for row in clock_trace),
            1,
            clock_trace,
        )
        self.assertEqual([row[0] for row in clock_trace].count(413005), 0, clock_trace)
        moved = runtime.fight.actors[7]
        expected_hour = before_hour % 12 + 1
        self.assertEqual(helper.states(moved)[6759], expected_hour, clock_trace)
        self.assertEqual(moved.effect_stats[55], expected_hour, clock_trace)
        self.assertTrue(event.get("on_hours"))
        self.assertTrue(packets)
