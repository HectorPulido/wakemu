"""Lawful inverse clock and coupled native2237 producer qualification."""
import unittest
from unittest.mock import patch
import test_xelor_runtime_pipeline as helpers
import test_combat_xelor_own_hour_runtime as paths
from wakfu_server.combat_effect_dispatch import EffectDispatcher
from wakfu_server.combat_event_replay import NativeEventReplay


class XelorHourBoundariesCandidateTests(unittest.TestCase):
    def test_inverse_paid_wp_on_real_tock_changes_hour_and_owned_layout(self):
        h = helpers.XelorRuntimePipelineTests()
        observations = {}
        for enabled in (False, True):
            data = h.fixture(passives=(7184,) if enabled else ())
            data = h.next_owned_turn(h.adopt(data, h.dial(data).fight))
            actor = data[2].actors[7]
            self.assertEqual(h.states(actor).get(6772), 1 if enabled else None)
            self.assertEqual(h.states(actor)[6759], 12)
            before_wp = actor.effect_stats[4]
            before_ap = actor.ap
            trace = []
            original = EffectDispatcher.execute

            def observe(dispatcher, invocation, **kwargs):
                result = original(dispatcher, invocation, **kwargs)
                if invocation.reference in (
                    314230,
                    314349,
                    314350,
                    314351,
                    314352,
                    349618,
                    413421,
                    413424,
                ):
                    trace.append(
                        (
                            invocation.reference,
                            invocation.caster_id,
                            invocation.target_id,
                            bool(result),
                        )
                    )
                return result

            with patch.object(EffectDispatcher, "execute", observe):
                tx = h.cast(data, 775, data[2].actors[-7].position, action_id=41)
            self.assertEqual(tx.fight.actors[7].effect_stats[4], before_wp - 1)
            self.assertEqual(tx.fight.actors[7].ap, before_ap - 1)
            self.assertEqual(h.states(tx.fight.actors[7])[6759], 11 if enabled else 1)
            completed = {ref for ref, caster, target, ok in trace if ok}
            self.assertEqual(314349 in completed, enabled, trace)
            self.assertEqual(314230 in completed, not enabled, trace)
            layout = {
                row["reference"]: tuple(row["cell"])
                for row in tx.fight.native_effect_areas.values()
                if row.get("owner_id") == 7 and 1546 <= row["reference"] <= 1558
            }
            self.assertTrue(set(range(1546, 1558)) <= set(layout), layout)
            self.assertNotIn(6759, h.states(tx.fight.actors[-7]))
            observations[enabled] = layout[1558]
        self.assertNotEqual(observations[False], observations[True])

    def test_owned_hour_actual_damage_and_coupled_master_2237_producer(self):
        h = helpers.XelorRuntimePipelineTests()
        observations = {}
        for enabled in (False, True):
            data = h.fixture(passives=(758, 7187) if enabled else (758,))
            data = h.adopt(data, h.cast(data, 5345, (-11, -7, -1)).fight)
            trace, events = [], []
            original = EffectDispatcher.execute
            replay = NativeEventReplay.__call__

            def observe(dispatcher, invocation, **kwargs):
                fight = dispatcher.native_retention.fight
                hp = fight.actors[7].hp
                result = original(dispatcher, invocation, **kwargs)
                if invocation.reference in (349619, 349671, 349674, 349667):
                    trace.append(
                        (
                            invocation.reference,
                            invocation.caster_id,
                            invocation.target_id,
                            bool(result),
                            hp,
                            fight.actors[7].hp,
                        )
                    )
                return result

            def observe_event(instance, source, **kwargs):
                if 2237 in source.event_ids:
                    events.append((source.channel, source.caster_id, source.target_id))
                return replay(instance, source, **kwargs)

            with patch.object(EffectDispatcher, "execute", observe), patch.object(
                NativeEventReplay, "__call__", observe_event
            ):
                for _ in range(8):
                    fight = data[2]
                    centers = [
                        tuple(row["cell"])
                        for row in fight.native_effect_areas.values()
                        if row.get("owner_id") == 7 and row["reference"] == 1558
                    ]
                    self.assertEqual(len(centers), 1)
                    if fight.actors[7].position == centers[0]:
                        break
                    path = paths.XelorOwnHourRuntimeTests.path(fight, centers[0])
                    steps = path[: fight.actors[7].mp]
                    origin = fight.actors[7].position
                    fight.move(3, 7, steps)
                    from wakfu_server.combat_area_transaction import (
                        prepare_area_movement,
                    )

                    preview, _ = prepare_area_movement(
                        data[0],
                        {-7: data[1]},
                        fight,
                        data[3],
                        actor_id=7,
                        action_id=40,
                        path=steps,
                        origin=origin,
                        rng=data[4],
                    )
                    data = h.adopt(data, preview)
                    if preview.actors[7].position != centers[0]:
                        data = h.next_owned_turn(data)
                else:
                    self.fail("Actual paid movement never reached owned current hour")
                data = h.next_owned_turn(data)
                start_rows = [r for r in trace if r[0] == 349667 and r[3]]
                self.assertEqual(bool(start_rows), enabled, trace)
                if enabled:
                    self.assertTrue(
                        all(r[1:3] == (7, 7) and r[5] < r[4] for r in start_rows), trace
                    )
                # Real paidWP clock progression, not a forged2237 notification.
                # First rollover consumes the authored opening7788 marker;
                # only the next rollover reaches349618/349619. Pay actual WP
                # and traverse actual turns instead of forging2237.
                for payment in range(4):
                    tx = h.cast(data, 2839, action_id=61 + payment)
                    data = h.adopt(data, tx.fight)
                    if events:
                        centers_after = [
                            tuple(row["cell"])
                            for row in tx.fight.native_effect_areas.values()
                            if row.get("owner_id") == 7 and row["reference"] == 1558
                        ]
                        self.assertEqual(centers_after, [tx.fight.actors[7].position])
                        break
                    data = h.next_owned_turn(data)
                    for approach in range(8):
                        fight = data[2]
                        # 2237 fires after the new6759 value has relocated1558.
                        # Stand on the future actual native hour before paying,
                        # not the previous center vacated by that payment.
                        next_hour = ((h.states(fight.actors[7])[6759] + 4 - 1) % 12) + 1
                        current = [
                            tuple(row["cell"])
                            for row in fight.native_effect_areas.values()
                            if row.get("owner_id") == 7
                            and row["reference"] == 1545 + next_hour
                        ]
                        self.assertEqual(len(current), 1)
                        if fight.actors[7].position == current[0]:
                            break
                        steps = paths.XelorOwnHourRuntimeTests.path(fight, current[0])[
                            : fight.actors[7].mp
                        ]
                        origin = fight.actors[7].position
                        fight.move(3, 7, steps)
                        preview, _ = prepare_area_movement(
                            data[0],
                            {-7: data[1]},
                            fight,
                            data[3],
                            actor_id=7,
                            action_id=80 + payment,
                            path=steps,
                            origin=origin,
                            rng=data[4],
                        )
                        data = h.adopt(data, preview)
                        if preview.actors[7].position != current[0]:
                            data = h.next_owned_turn(data)
                    else:
                        self.fail(
                            "Paid return to current hour failed before native rollover"
                        )
                self.assertTrue(events, trace)
                self.assertTrue(any(r[0] == 349619 and r[3] for r in trace), trace)
                positive_entry = any(r[0] == 349674 and r[3] for r in trace)
                self.assertEqual(positive_entry, enabled, (trace, events))
                self.assertNotIn(7789, h.states(tx.fight.actors[-7]))
                observations[enabled] = sum(r[4] - r[5] for r in start_rows)
        self.assertEqual(observations[False], 0)
        self.assertGreater(observations[True], 0)
