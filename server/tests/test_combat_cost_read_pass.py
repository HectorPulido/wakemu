"""Focused cost-source ownership, callback freshness and fallback checks."""
from dataclasses import replace
import unittest
from unittest.mock import patch

from test_combat_ordinary_phase_read_pass import PhaseReadPassSemanticTests
from wakfu_server import combat_ordinary_events as ordinary
from wakfu_server.combat_cost_payment_events import NativeCostPaymentEvents, _payment
from wakfu_server.combat_effect_dispatch import EffectInvocation


class CostReadPassTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        PhaseReadPassSemanticTests.setUpClass()

    def fixture(self):
        case = PhaseReadPassSemanticTests().fixture()
        case.events = NativeCostPaymentEvents.from_healing(case.events)
        case.inv = replace(
            case.inv,
            reference=-1,
            level=-1,
            native_retained_container={"present": False},
        )
        case.effect = dict(
            effect_class=30, native_effect_flags=[], native_costs=dict(ap=2, mp=0, wp=0)
        )
        return case

    def phase(self, case):
        return case.events.phase(
            case.effect,
            case.inv,
            uid=-1,
            value=2,
            channel=3,
            _event_ids=case.f.source().event_ids,
        )

    def test_cost_uses_one_view_without_observers_and_resets_context(self):
        case = self.fixture()
        case.fight.native_owned_group_effects[900]["native_subscription_masks"] = [
            None
        ] * 7
        self.assertIs(case.events.replay, case.replay)
        with patch.object(case.retention, "view", wraps=case.retention.view) as view:
            self.phase(case)
        self.assertEqual(view.call_count, 1)
        self.assertIsNone(case.replay._read_pass)
        self.assertIsNone(_payment.get())

    def test_cost_callback_added_listener_is_seen_by_later_global_delivery(self):
        case = self.fixture()
        masks = [list(case.f.source().event_ids)] * 7
        case.fight.native_owned_group_effects[900]["native_subscription_masks"] = masks
        case.retention.metadata["effects"]["308265"]["event_global_subscription"] = True
        seen, created = [], []

        def activation(invocation, **kwargs):
            seen.append(invocation.target_id)
            if invocation.target_id == 7 and not created:
                case.f.dispatcher.execute(
                    EffectInvocation(308265, 1, -7, -7, (1, 0, 0))
                )
                uid = max(case.fight.native_owned_group_effects)
                case.fight.native_owned_group_effects[uid][
                    "native_subscription_masks"
                ] = masks
                created.append(uid)
            return False

        case.f.dispatcher.execute_activation = activation
        self.phase(case)
        self.assertTrue(created)
        self.assertIn(-7, seen)
        self.assertIsNone(case.replay._read_pass)
        self.assertIsNone(_payment.get())

    def test_custom_delivery_keeps_fresh_cost_copies_and_exception_cleanup(self):
        case = self.fixture()
        descriptors = []

        def replay(source, *, authority):
            descriptors.append(dict(source.cost_source))
            source.cost_source["sentinel"] = True
            if len(descriptors) == 2:
                raise RuntimeError("custom cost callback")
            return ()

        case.events.replay = replay
        with self.assertRaisesRegex(RuntimeError, "custom cost callback"):
            self.phase(case)
        self.assertEqual(len(descriptors), 2)
        self.assertNotIn("sentinel", descriptors[1])
        self.assertIsNone(_payment.get())
        self.assertIsNone(case.replay._read_pass)

        class CustomCost(NativeCostPaymentEvents):
            pass

        custom = CustomCost.from_healing(case.events)
        self.assertFalse(ordinary._native_phase_replay_source(custom))

    def test_inherited_death_finisher_delegate_preserves_cost_transformation(self):
        case = self.fixture()
        seen = []
        case.events.replay = lambda source, **kw: seen.append(source.cost_source)
        descriptor = dict(runner_class="eWf", action_costs=dict(ap=2, mp=0, wp=0))
        token = _payment.set(descriptor)
        try:
            case.events._event_delivery_replay()(
                case.f.source(), authority=case.events.authority
            )
        finally:
            _payment.reset(token)
        self.assertEqual(seen, [descriptor])
        self.assertIsNot(seen[0], descriptor)


if __name__ == "__main__":
    unittest.main()
