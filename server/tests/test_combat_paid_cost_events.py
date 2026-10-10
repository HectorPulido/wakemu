"""Actual paid receipt selection; no resource mutation or special flag guesses."""
import unittest
from types import SimpleNamespace
from wakfu_server.combat.combat_cost_payment_events import (
    payment_event_ids,
    replay_paid_spell_costs,
)


class PaidCostEventsTests(unittest.TestCase):
    def test_native_fresh_payment_masks(self):
        for costs, expected in (
            ({"ap": 0, "mp": 0, "wp": 0}, (0,)),
            ({"ap": 2, "mp": 0, "wp": 0}, (0, 55)),
            ({"ap": 0, "mp": 1, "wp": 0}, (0, 65)),
            ({"ap": 0, "mp": 0, "wp": 1}, (0, 60)),
            ({"ap": 2, "mp": 1, "wp": 1}, (0, 55, 60, 65)),
        ):
            self.assertEqual(payment_event_ids(costs), expected)

    def test_receipt_preserves_paid_cost_source_and_does_not_pay_again(self):
        calls = []
        events = SimpleNamespace(phase=lambda *args, **kw: calls.append((args, kw)))
        dispatcher = SimpleNamespace(native_cost_payment_events_factory=lambda: events)
        plan = {"actor_id": 7, "costs": {"ap": 3, "mp": 0, "wp": 1}}
        replay_paid_spell_costs(dispatcher, plan)
        self.assertEqual(plan["costs"], {"ap": 3, "mp": 0, "wp": 1})
        self.assertEqual([kw["channel"] for _, kw in calls], [3, 4])
        for args, kw in calls:
            definition, invocation = args
            self.assertEqual(definition["native_costs"], plan["costs"])
            self.assertEqual(
                (invocation.reference, invocation.caster_id, invocation.target_id),
                (-1, 7, 7),
            )
            self.assertEqual(
                (kw["uid"], kw["value"], kw["_event_ids"]), (-1, 65539, (0, 55, 60))
            )

    def test_invalid_costs_never_publish(self):
        for costs in (
            {"ap": -1, "mp": 0, "wp": 0},
            {"ap": True, "mp": 0, "wp": 0},
            {"ap": 128, "mp": 0, "wp": 0},
            {"ap": 1},
        ):
            with self.assertRaises(ValueError):
                payment_event_ids(costs)
