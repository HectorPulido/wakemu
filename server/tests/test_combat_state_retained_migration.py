"""Native state membership and retained retirement contracts on current execution."""
import copy
from dataclasses import asdict, replace
import struct
from types import SimpleNamespace
import unittest

from wakfu_server.combat_state_ledger import StateLedger, StateTimeline
from wakfu_server.combat_state_timing import StateTimer
from wakfu_server.combat_retained_effects import RetainedEffect
from wakfu_server.combat_retained_runtime import (
    group_payload,
    remove_owned_group,
    remove_owned_stat,
)
from wakfu_server.combat_native_delay_queue import fresh_queue


def state_catalog():
    base = dict(
        maximum_level=100,
        additive=True,
        replace=True,
        refresh=False,
        protected=False,
        duration_base=-1,
        duration_per_level=0,
        realtime_duration_base=0,
        realtime_duration_per_level=0,
        clock_actor="caster",
        tick_at_turn_end=False,
        skip_turn_timer=False,
        effect_ids=[99],
    )
    return dict(
        states={
            "1": dict(base),
            "2": dict(base, duration_base=0),
            "3": dict(base, duration_base=1),
            "4": dict(base, duration_base=0, realtime_duration_base=30),
        },
        effects={"99": dict(minimum_level=0, maximum_level=100)},
    )


def group_world():
    payload = group_payload(
        uid=901,
        base_uid=800,
        generic_effect=350552,
        caster_id=7,
        target_id=None,
        cell=(4, 5, 0),
        container_type=None,
        container_id=None,
        timing_payload=b"\x08\x00",
    )
    entry = RetainedEffect(
        901, None, 949, 350552, manager_id=7, container_present=False
    )
    queue = fresh_queue()
    queue["next_sequence"] = 3
    queue["entries"] = [
        dict(
            sequence=sequence,
            uid=uid,
            clock_id=7,
            round=2,
            phase="start",
            invocation={},
        )
        for sequence, uid in ((1, 901), (2, 902))
    ]
    return SimpleNamespace(
        id=12,
        native_owned_group_effects={
            901: dict(
                target_id=None, effect_class=949, state_uid=None, payload=payload.hex()
            ),
        },
        native_retained_records={901: asdict(entry)},
        native_retained_order=[901],
        native_delay_queue=queue,
        # Separately executed children must survive retirement of their group.
        owned_stat_effects={902: dict(state_uid=None, target_id=7, value=3)},
    )


class StateRetainedMigrationTests(unittest.TestCase):
    def state_sequence(self, *, failing_callback=False):
        ledger, catalog, events = StateLedger(7), state_catalog(), []
        ledger.apply(catalog, 1, 5, caster_id=8, uid=10)
        instant = ledger.apply(
            catalog, 2, 3, caster_id=8, uid=11, applying_effect_has_delay=False
        )
        self.assertFalse(instant.applied.retained)
        self.assertEqual([entry.uid for entry in ledger.entries], [10])

        def before_replace(old):
            events.append(("before", old.uid, tuple(e.uid for e in ledger.entries)))
            ledger.apply(
                catalog, 2, 2, caster_id=9, uid=13, applying_effect_has_delay=True
            )
            events.append(("nested", tuple(e.uid for e in ledger.entries)))
            removed = ledger.remove(old.uid)
            events.append(("removed", removed.uid))
            if failing_callback:
                raise ValueError("Replacement callback rejected")

        if failing_callback:
            with self.assertRaisesRegex(ValueError, "callback rejected"):
                ledger.apply(
                    catalog, 1, 5, caster_id=9, uid=12, before_replace=before_replace
                )
            self.assertEqual([e.uid for e in ledger.entries], [13])
            return tuple(ledger.entries), events
        applied = ledger.apply(
            catalog, 1, 5, caster_id=9, uid=12, before_replace=before_replace
        )
        self.assertEqual(applied.applied.level, 10)
        self.assertEqual([e.uid for e in ledger.entries], [13, 12])
        timed = ledger.apply(
            catalog,
            3,
            1,
            caster_id=8,
            uid=14,
            timeline=StateTimeline(1, 8, 0, 0, "active"),
        )
        self.assertEqual(timed.applied.timer, StateTimer(8, 2, "start"))
        self.assertEqual(ledger.expire(actor_id=7, round_number=2, phase="start"), ())
        self.assertEqual(ledger.expire(actor_id=8, round_number=2, phase="end"), ())
        events.append(
            (
                "expired",
                tuple(
                    e.uid
                    for e in ledger.expire(actor_id=8, round_number=2, phase="start")
                ),
            )
        )
        realtime = ledger.apply(catalog, 4, 1, caster_id=8, uid=15).applied
        clocked = ledger.install_realtime_clock(15, deadline_ms=123456, in_combat=True)
        self.assertEqual(clocked.realtime_deadline_ms, 123456)
        self.assertIsNone(clocked.timer)
        self.assertNotEqual(clocked, realtime)
        unscheduled = ledger.apply(catalog, 3, 1, caster_id=8, uid=16).applied
        scheduled = replace(unscheduled, timer=StateTimer(8, 3, "end"))
        ledger.bind_registered_timer(unscheduled, scheduled)
        events.append(
            (
                "cleanup",
                tuple(
                    e.uid
                    for e in ledger.expire(
                        actor_id=999, round_number=4, phase="start", round_cleanup=True
                    )
                ),
            )
        )
        self.assertEqual(ledger.remove(13).uid, 13)
        self.assertIsNone(ledger.remove(999))
        self.assertEqual(events[-2:], [("expired", (14,)), ("cleanup", (16,))])
        self.assertEqual([e.uid for e in ledger.entries], [12, 15])
        return tuple(ledger.entries), events

    def test_apply_recursive_replace_remove_and_native_clocks(self):
        entries, events = self.state_sequence()
        self.assertEqual([entry.uid for entry in entries], [12, 15])
        self.assertEqual(
            events[:3], [("before", 10, (10,)), ("nested", (10, 13)), ("removed", 10)]
        )

    def test_callback_failure_preserves_native_partial_preview(self):
        entries, events = self.state_sequence(failing_callback=True)
        self.assertEqual([entry.uid for entry in entries], [13])
        self.assertEqual(events[-1], ("removed", 10))

    def native_state_delivery(self, *, fail_child=False):
        from itertools import count
        from wakfu_server.combat_state import Actor, Fight
        from wakfu_server.spell_audit import states_catalog
        from wakfu_server.combat_state_handler import (
            NativeStateHandler,
            StateCarrierContext,
        )
        from wakfu_server.combat_effect_dispatch import (
            EffectInvocation,
            EffectDispatcher,
            run_effect_transaction,
            UnsupportedEffectExecution,
        )
        from wakfu_server.combat_conditions import ConditionContext
        from wakfu_server.fight_checkpoint_store import snapshot

        actors = [
            Actor(7, 0, (0, 0, 0), 100, 6, 3, 10, 1, 3, True),
            Actor(-7, 1, (1, 0, 0), 100, 6, 3, 5, 1),
        ]
        fight = Fight(
            77,
            actors,
            {a.position for a in actors},
            {0: {actors[0].position}, 1: {actors[1].position}},
        )
        fight.ready(3)
        catalog, packets, children = states_catalog(), [], []
        invocation = EffectInvocation(91, 1, 7, 7, (0, 0, 0))
        context = lambda *args: StateCarrierContext(
            -1, 0, False, None, 100, False, False, False, 0, None
        )
        if fail_child:
            effects = dict(catalog["effects"])
            effects["91"] = dict(
                effect_class=304,
                parameters=[3442, 0, 20, 0, -1, 0],
                parameter_count=3,
                probability_base=100,
                probability_per_level=0,
                minimum_level=1,
                maximum_level=200,
                criteria="",
                children=[],
            )
            initial = snapshot(fight)

            def factory(preview):
                dispatcher = EffectDispatcher(
                    effects,
                    {},
                    resolve=lambda effect, inv: (inv,),
                    condition_context=lambda _: ConditionContext({}),
                    probability_accepts=lambda probability, inv: probability == 100,
                    group_cells=lambda *args: (),
                    actor_position=lambda actor_id: preview.actors[actor_id].position,
                )
                dispatcher.handlers[304] = NativeStateHandler(
                    preview,
                    [],
                    catalog,
                    action_id=1,
                    allocate_uid=lambda: 200,
                    execute_child=dispatcher.execute,
                    context=context,
                )
                return dispatcher

            with self.assertRaisesRegex(UnsupportedEffectExecution, "No handler"):
                run_effect_transaction(fight, [invocation], factory)
            self.assertEqual(snapshot(fight), initial)
            self.assertEqual(fight.actors[7].state_ledger.entries, ())
            self.assertEqual(fight.state_wire_payloads, {})
        else:
            uids = count(200)
            handler = NativeStateHandler(
                fight,
                packets,
                catalog,
                action_id=1,
                allocate_uid=lambda: next(uids),
                execute_child=children.append,
                context=context,
            )
            for _ in range(2):
                self.assertTrue(
                    handler(
                        dict(effect_class=304),
                        {"parameters": [3442, 20, -1]},
                        invocation,
                    )
                )
            self.assertEqual([packet[0] for packet in packets], [12613, 13560, 12613])
            self.assertEqual(set(fight.state_wire_payloads), {201})
            entry = fight.actors[7].state_ledger.entries[0]
            self.assertEqual((entry.reference, entry.uid, entry.level), (3442, 201, 40))
            self.assertTrue(children)
            relevant_events = [
                event for event in fight.events if event["kind"].startswith("state_")
            ]
            self.assertEqual(
                [event["kind"] for event in relevant_events],
                ["state_applied", "state_removed", "state_applied"],
            )
        return snapshot(fight), packets, children

    def test_real_state_handler_complete_state_events_packets_and_children(self):
        self.native_state_delivery()

    def test_failed_real_child_transaction_preserves_complete_original_fight(self):
        self.native_state_delivery(fail_child=True)

    def test_duplicate_uid_rejects_before_replacement_callback(self):
        ledger, catalog = StateLedger(7), state_catalog()
        ledger.apply(catalog, 1, 1, caster_id=8, uid=1)
        before = ledger.entries
        calls = []
        with self.assertRaisesRegex(ValueError, "UID is already running"):
            ledger.apply(
                catalog,
                1,
                1,
                caster_id=8,
                uid=1,
                before_replace=lambda old: calls.append(old.uid),
            )
        self.assertEqual(calls, [])
        self.assertIs(ledger.entries, before)

    def test_timer_binding_uses_exact_original_object_not_equal_copy(self):
        ledger = StateLedger(7)
        original = ledger.apply(state_catalog(), 3, 1, caster_id=8, uid=1).applied
        equal_copy = replace(original)
        ledger.bind_registered_timer(
            equal_copy, replace(equal_copy, timer=StateTimer(8, 3, "end"))
        )
        self.assertIs(ledger.entries[0], original)
        self.assertIsNone(ledger.entries[0].timer)

    def group_sequence(self, *, failure=None):
        fight, packets = group_world(), []
        initial = copy.deepcopy(vars(fight))
        if failure == "payload":
            fight.native_owned_group_effects[901]["payload"] = "00"
            initial = copy.deepcopy(vars(fight))
        elif failure == "queue":
            fight.native_delay_queue["source"] = "invalid"
            initial = copy.deepcopy(vars(fight))
        error = None
        try:
            remove_owned_group(fight, packets, action_id=3, uid=901)
        except ValueError as caught:
            error = (type(caught).__name__, str(caught))
        if failure == "payload":
            self.assertEqual(vars(fight), initial)
            self.assertEqual(packets, [])
        elif failure == "queue":
            self.assertEqual(vars(fight), initial)
            self.assertEqual(len(packets), 1)
        else:
            self.assertIsNone(error)
            self.assertEqual(fight.native_owned_group_effects, {})
            self.assertEqual(fight.native_retained_records, {})
            self.assertEqual(fight.native_retained_order, [])
            self.assertEqual(
                [r["uid"] for r in fight.native_delay_queue["entries"]], [902]
            )
            self.assertEqual(fight.owned_stat_effects, initial["owned_stat_effects"])
        if packets:
            self.assertEqual(packets[0][0], 13560)
            self.assertEqual(struct.unpack(">qq", packets[0][1][-16:]), (7, 901))
        return vars(fight), packets, error

    def test_retained_group_packet_queue_population_and_children(self):
        self.group_sequence()

    def test_retained_group_preflight_and_cancellation_failures(self):
        for failure in ("payload", "queue"):
            with self.subTest(failure=failure):
                result = self.group_sequence(failure=failure)
                self.assertIsNotNone(result[-1])

    def stat_sequence(self, manager, *, malformed=False):
        fight = SimpleNamespace(
            owned_stat_effects={91: dict(target_id=7, value=3)},
            native_retained_records={91: dict(manager_id=manager)},
        )
        packets, events = [], []

        def remove(uid):
            events.append(("reverse", uid, fight.owned_stat_effects[uid]["value"]))
            del fight.owned_stat_effects[uid]
            packets.append(
                (123 if malformed else 13560, b"original" + struct.pack(">qq", 7, uid))
            )

        handler = SimpleNamespace(fight=fight, packets=packets, remove=remove)
        error = None
        try:
            remove_owned_stat(handler, 91)
        except ValueError as caught:
            error = (type(caught).__name__, str(caught))
        self.assertEqual(events, [("reverse", 91, 3)])
        self.assertEqual(fight.owned_stat_effects, {})
        if malformed:
            self.assertIsNotNone(error)
        else:
            self.assertIsNone(error)
            self.assertEqual(struct.unpack(">qq", packets[-1][1][-16:]), (manager, 91))
            self.assertEqual(
                packets, [(13560, b"original" + struct.pack(">qq", manager, 91))]
            )
        return vars(fight), events, packets, error

    def test_stat_reversal_and_manager_packet_rewrite(self):
        for manager in (7, 8):
            with self.subTest(manager=manager):
                self.stat_sequence(manager)

    def test_stat_invalid_post_reversal_delivery_preserves_native_partial_preview(self):
        self.stat_sequence(8, malformed=True)


if __name__ == "__main__":
    unittest.main()
