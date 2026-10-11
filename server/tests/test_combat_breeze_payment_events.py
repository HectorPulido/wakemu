"""Paid fad receipts preserve signed source identity without paying twice."""
import unittest
from types import SimpleNamespace
from dataclasses import replace
from wakfu_server.combat_breeze_payment_events import replay_paid_breeze_costs
from wakfu_server.combat_event_replay import NativeEventSource


class BreezePaymentEventTests(unittest.TestCase):
    def test_signed_payment_and_zero_change_keep_native_post_phases(self):
        for requested, actual in ((-200, -200), (23, 0)):
            rows = []
            events = SimpleNamespace(
                phase=lambda effect, invocation, **kw: rows.append(
                    (effect, invocation, kw)
                )
            )
            dispatcher = SimpleNamespace(
                native_breeze_payment_events_factory=lambda: events
            )
            plan = dict(
                actor_id=7,
                extra_resource_payment=(
                    dict(stat_id=111, requested_delta=requested, actual_delta=actual),
                ),
            )
            replay_paid_breeze_costs(dispatcher, plan)
            self.assertEqual([row[2]["channel"] for row in rows], [3, 4])
            self.assertEqual(rows[0][1].caster_id, 7)
            self.assertEqual(rows[0][1].target_id, 7)
            self.assertEqual(rows[0][2]["value"], requested)
            self.assertEqual(rows[0][2]["_event_ids"], (0, 2246))
            source = NativeEventSource(
                -1,
                -1,
                requested,
                7,
                7,
                (0, 0, 0),
                (0, 2246),
                3,
                7,
                None,
                False,
                False,
                False,
                True,
                cost_source=rows[0][2]["_cost_source"],
                native_container={"present": False},
                native_definition_present=False,
                native_execution_status=-1,
            )
            source.validate()
            with self.assertRaises(ValueError):
                replace(source, caster_id=8).validate()
            with self.assertRaises(ValueError):
                replace(source, value=requested + 1).validate()

    def test_no_receipt_emits_nothing_and_missing_authority_rejects(self):
        replay_paid_breeze_costs(SimpleNamespace(), {})
        with self.assertRaisesRegex(ValueError, "event authority"):
            replay_paid_breeze_costs(
                SimpleNamespace(),
                dict(
                    extra_resource_payment=(
                        dict(stat_id=111, requested_delta=-200, actual_delta=-200),
                    )
                ),
            )
