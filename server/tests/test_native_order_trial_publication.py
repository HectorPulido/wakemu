"""Candidate event observation is inside guarded shared publication."""

from types import SimpleNamespace as Namespace
import unittest
from unittest.mock import Mock, patch

from wakfu_server.combat_shared import Registry
from wakfu_server import combat_retained_gc_boundary
from wakfu_server import combat_invariant_observation
from wakfu_server import combat_checkpoint_publication
from wakfu_server import native_order_trial_events
from wakfu_server import native_order_trial_presentation
from wakfu_server import native_order_trial_orders
from wakfu_server import native_order_trial_encounter


class NativeOrderTrialPublicationTests(unittest.TestCase):
    def case(self, *, marker=True):
        prefix = [
            {"kind": "old-event", "sequence": 1},
            {"kind": "old-event", "sequence": 2},
        ]
        current = Namespace(events=list(prefix), sequence=2)
        candidate = Namespace(
            events=list(prefix) + [{"kind": "action", "sequence": 3}],
            sequence=3,
        )
        if marker:
            candidate.native_order_trial = {"candidate": True}
        shared = Namespace(fight=current, ack=object())
        registry = Registry(lambda _session: True)
        order = []
        observed_batches = []

        def accepted(_shared, fight, runtime, packets):
            order.append("accepted")
            fight.events.append({"kind": "accepted", "sequence": 4})
            fight.sequence = 4
            return fight, runtime, packets

        def synchronized(_shared, fight, runtime, packets):
            order.append("synchronized")
            fight.events.append({"kind": "synchronized", "sequence": 5})
            fight.sequence = 5
            return packets

        def observer(fight, *, events):
            order.append("observer")
            observed_batches.append(events)
            self.assertIs(fight, candidate)
            self.assertEqual(
                [event["kind"] for event in events],
                ["action", "accepted", "synchronized"],
            )
            self.assertNotIn(prefix[0], events)
            return len(events)

        def advance(fight, *, events):
            order.append("advance")
            self.assertIs(fight, candidate)
            self.assertIs(events, observed_batches[-1])
            return False

        def prepare_markers(_fight, _runtime, packets):
            order.append("presentation")
            return packets

        with patch.object(
            registry, "_prepare_accepted", side_effect=accepted
        ), patch.object(
            registry, "_synchronize_defeated_current", side_effect=synchronized
        ), patch.object(
            registry, "_accepted_ack", side_effect=lambda *_args, **_kwargs: object()
        ), patch.object(
            combat_retained_gc_boundary,
            "prepare_retired_gc",
            side_effect=lambda *_: order.append("gc"),
        ), patch.object(
            combat_invariant_observation,
            "observe_prepared_boundary",
            side_effect=lambda *_args, **_kwargs: order.append("boundary"),
        ), patch.object(
            combat_checkpoint_publication,
            "persist_prepared",
            side_effect=lambda *_args: order.append("persist"),
        ), patch.object(
            native_order_trial_events, "observe_pending", side_effect=observer
        ) as observe, patch.object(
            native_order_trial_presentation,
            "prepare",
            side_effect=prepare_markers,
        ), patch.object(
            native_order_trial_orders, "advance", side_effect=advance
        ), patch.object(
            native_order_trial_encounter,
            "finish_normal",
            side_effect=lambda *_: order.append("finish"),
        ):
            prepared = registry._prepare_publication(
                shared, candidate, None, (), operation="test-order-trial"
            )
        return shared, candidate, prepared, observe, order

    def test_candidate_suffix_is_observed_after_preparation_before_persistence(self):
        shared, candidate, prepared, observe, order = self.case()
        self.assertEqual(prepared.fight, candidate)
        self.assertEqual(shared.fight.sequence, 2)
        self.assertEqual(
            order[:5],
            ["accepted", "synchronized", "observer", "advance", "presentation"],
        )
        self.assertLess(order.index("observer"), order.index("persist"))
        self.assertLess(order.index("presentation"), order.index("finish"))
        self.assertLess(order.index("finish"), order.index("persist"))
        observe.assert_called_once()

    def test_observer_rejection_prevents_checkpoint_persistence(self):
        current = Namespace(events=[{"kind": "old-event", "sequence": 1}], sequence=1)
        candidate = Namespace(
            events=[
                {"kind": "old-event", "sequence": 1},
                {"kind": "action", "sequence": 2},
            ],
            sequence=2,
            native_order_trial={"candidate": True},
        )
        shared = Namespace(fight=current, ack=object())
        registry = Registry(lambda _session: True)
        order = []

        def accepted(_shared, fight, runtime, packets):
            order.append("accepted")
            return fight, runtime, packets

        def synchronized(_shared, fight, runtime, packets):
            order.append("synchronized")
            return packets

        with patch.object(
            registry, "_prepare_accepted", side_effect=accepted
        ), patch.object(
            registry, "_synchronize_defeated_current", side_effect=synchronized
        ), patch.object(
            registry, "_accepted_ack", return_value=object()
        ), patch.object(
            combat_retained_gc_boundary, "prepare_retired_gc"
        ), patch.object(
            combat_invariant_observation, "observe_prepared_boundary"
        ), patch.object(
            combat_checkpoint_publication, "persist_prepared"
        ) as persist, patch.object(
            native_order_trial_events,
            "observe_pending",
            side_effect=ValueError("candidate outcome rejected"),
        ) as observe, patch.object(
            native_order_trial_presentation,
            "prepare",
            side_effect=lambda _fight, _runtime, packets: packets,
        ), patch.object(
            native_order_trial_orders, "advance"
        ) as advance:
            with self.assertRaisesRegex(ValueError, "candidate outcome rejected"):
                registry._prepare_publication(
                    shared, candidate, None, (), operation="test-rejected-order"
                )
        self.assertIs(shared.fight, current)
        self.assertEqual(order, ["accepted", "synchronized"])
        observe.assert_called_once()
        advance.assert_not_called()
        persist.assert_not_called()

    def test_ordinary_fight_skips_order_observer(self):
        current = Namespace(events=[], sequence=0)
        candidate = Namespace(events=[], sequence=0)
        shared = Namespace(fight=current, ack=object())
        registry = Registry(lambda _session: True)
        order = []
        with patch.object(
            registry,
            "_prepare_accepted",
            side_effect=lambda _shared, fight, runtime, packets: (
                fight,
                runtime,
                packets,
            ),
        ), patch.object(
            registry,
            "_synchronize_defeated_current",
            side_effect=lambda _shared, _fight, _runtime, packets: packets,
        ), patch.object(
            registry, "_accepted_ack", return_value=object()
        ), patch.object(
            combat_retained_gc_boundary, "prepare_retired_gc"
        ), patch.object(
            combat_invariant_observation, "observe_prepared_boundary"
        ), patch.object(
            combat_checkpoint_publication,
            "persist_prepared",
            side_effect=lambda *_args: order.append("persist"),
        ), patch.object(
            native_order_trial_events, "observe_pending"
        ) as observe, patch.object(
            native_order_trial_orders, "advance"
        ) as advance:
            with patch.object(
                native_order_trial_presentation,
                "prepare",
                side_effect=lambda _fight, _runtime, packets: packets,
            ):
                prepared = registry._prepare_publication(
                    shared, candidate, None, (), operation="ordinary-combat"
                )
        self.assertIs(prepared.fight, candidate)
        observe.assert_not_called()
        advance.assert_not_called()
        self.assertEqual(order, ["persist"])


if __name__ == "__main__":
    unittest.main()
