import unittest
from wakfu_server.combat_trigger_masks import (
    match_trigger_masks,
    plan_trigger_dispatch,
    TriggerSubscription,
    UnknownTriggerRouting,
)


class NativeTriggerMaskTests(unittest.TestCase):
    def masks(self, index):
        return tuple(frozenset({71}) if i == index else None for i in range(7))

    def test_native_standard_channel_matrix(self):
        for channel, index in ((1, 0), (2, 1), (3, 3), (4, 2), (5, 4), (6, 5)):
            self.assertEqual(
                match_trigger_masks(
                    self.masks(index), event_bits={71}, channel=channel
                ),
                "remove" if channel == 4 else "apply",
            )
            self.assertIsNone(
                match_trigger_masks(self.masks(index), event_bits={72}, channel=channel)
            )

    def test_alternate_routing_and_emission_mask_is_not_subscription(self):
        self.assertEqual(
            match_trigger_masks(
                self.masks(0), event_bits={71}, channel=10, routing="aZw"
            ),
            "apply",
        )
        self.assertEqual(
            match_trigger_masks(
                self.masks(2), event_bits={71}, channel=41, routing="aZx"
            ),
            "remove",
        )
        self.assertIsNone(
            match_trigger_masks(self.masks(6), event_bits={71}, channel=1)
        )
        with self.assertRaises(UnknownTriggerRouting):
            match_trigger_masks(
                self.masks(4), event_bits={71}, channel=50, routing="aZw"
            )

    def test_priority_order_and_explicit_source_exclusions(self):
        subscriptions = [
            TriggerSubscription(1, 300, 10, self.masks(0), 2),
            TriggerSubscription(2, 200, 10, self.masks(0), 2),
            TriggerSubscription(3, 100, 20, self.masks(0), 3),
            TriggerSubscription(4, 400, 10, self.masks(0), 4),
        ]
        plan = plan_trigger_dispatch(
            subscriptions,
            owner_id=10,
            event_bits={71},
            channel=1,
            excluded_instance_ids=frozenset({1}),
        )
        self.assertEqual([p.subscription.instance_id for p in plan], [4, 2])

    def test_missing_mask_is_empty_but_wrong_shape_is_unknown(self):
        self.assertIsNone(match_trigger_masks((None,) * 7, event_bits={71}, channel=1))
        with self.assertRaises(UnknownTriggerRouting):
            match_trigger_masks([], event_bits={71}, channel=1)
