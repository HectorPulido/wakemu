"""Native retained marker projection for an accepted order-trial checkpoint."""

from copy import deepcopy
import struct
import unittest
from types import SimpleNamespace

from wakfu_server import native_order_trial_checkpoint as checkpoint
from wakfu_server import native_order_trial_presentation as presentation


class NativeOrderTrialPresentationTests(unittest.TestCase):
    def fixture(self):
        from native_order_trial_runtime_fixture import create_area768_fixture
        from wakfu_server import combat_runtime_messages

        return create_area768_fixture(), combat_runtime_messages.RuntimeMessages

    @staticmethod
    def state_levels(fight):
        actor = fight.actors[7]
        return {
            entry.reference: entry.level
            for entry in actor.state_ledger.entries
            if entry.reference in presentation.ROOTS
        }

    def test_native_markers_follow_checkpoint_score_and_keep_delivery_prefix(self):
        context, runtime_type = self.fixture()
        with context as (case, _dispatcher, factory):
            fight = case.fight
            runtime = runtime_type(
                fight,
                expiration_runtime_factory=lambda *, action_id: factory,
            )
            self._exercise(case, fight, runtime, factory)

    def _exercise(self, case, fight, runtime, factory):
        packets = presentation.prepare(fight, runtime, ())

        initial = self.state_levels(fight)
        self.assertEqual(initial.get(3050, 0), 0)
        self.assertEqual(
            {reference: initial[reference] for reference in (3051, 3056, 3060)},
            {3051: 1, 3056: 1, 3060: 1},
        )
        self.assertIn((13420, struct.pack(">i", fight.id)), packets)
        prefix = runtime.last_native_delivery
        self.assertTrue(prefix)

        classification = {
            "action": "bake",
            "arguments": {"target_id": -301},
            "source": "synthetic checkpoint fixture; not a native bake producer",
        }
        for action, arguments in (
            ("spawn", {"target_id": -301, "color": "green"}),
            ("pickup", {"ingredient": "pepper"}),
            ("tenderize", {"target_id": -301}),
            ("garnish", {"target_id": -301}),
        ):
            fixture_event = fight._event(
                "test_native_order_trial_action", action=action
            )
            self.assertTrue(
                checkpoint.observe(
                    fight,
                    fixture_event,
                    classify=lambda _candidate, _event, action=action, arguments=arguments: {
                        "action": action,
                        "arguments": arguments,
                        "source": "synthetic checkpoint fixture; not a native action producer",
                    },
                )
            )
        event = fight._event("test_native_order_trial_bake", actor_id=7)
        self.assertTrue(
            checkpoint.observe(
                fight, event, classify=lambda _candidate, _event: classification
            )
        )
        self.assertFalse(
            checkpoint.observe(
                fight,
                event,
                classify=lambda *_: self.fail("receipt replay classified twice"),
            )
        )

        updated = presentation.prepare(fight, runtime, ())
        current = self.state_levels(fight)
        self.assertEqual(current.get(3050), 1)  # five earned points / five per level
        self.assertEqual(current.get(3060), None)  # served request marker removed
        self.assertEqual(current.get(3051), 1)
        self.assertEqual(current.get(3056), 1)
        self.assertEqual(runtime.last_native_delivery[: len(prefix)], prefix)
        self.assertTrue(any(opcode == 13420 for opcode, _body in updated))
        self.assertGreater(len(runtime.last_native_delivery), len(prefix))

        stable_delivery = runtime.last_native_delivery
        dispatcher, _outbox = factory(
            fight, {"native_retained_container": {"present": False}}
        )
        self.assertFalse(presentation.synchronize(fight, dispatcher))
        self.assertEqual(runtime.last_native_delivery, stable_delivery)

        malformed = deepcopy(fight)
        malformed.native_order_trial["rules"]["rules_sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            presentation.desired(malformed)
        foreign = deepcopy(fight)
        foreign.actors[7].owner_id += 1
        with self.assertRaisesRegex(ValueError, "admitted player"):
            presentation.desired(foreign)

        def remove_marker(reference):
            dispatcher, _outbox = factory(
                fight, {"native_retained_container": {"present": False}}
            )
            entries = [
                entry
                for entry in fight.actors[7].state_ledger.entries
                if entry.reference == reference
            ]
            self.assertEqual(len(entries), 1)
            dispatcher.native_retention.removal(
                dispatcher.native_retention.view()
            ).remove((entries[0].uid,))

        # A dead owner without a finished reducer state still follows ordinary
        # synchronization and receives a missing marker.
        remove_marker(3051)
        fight.actors[7].hp = 0
        updated_dead = presentation.prepare(fight, runtime, ())
        self.assertTrue(any(opcode == 13420 for opcode, _body in updated_dead))
        self.assertEqual(self.state_levels(fight).get(3051), 1)

        # The actual checkpoint finish action makes terminal state durable.
        # Once final cleanup has killed the owner, prepare must preserve the
        # existing packet prefix without constructing another native factory.
        remove_marker(3051)
        finish = fight._event("test_native_order_trial_finish", actor_id=7)
        self.assertTrue(
            checkpoint.observe(
                fight,
                finish,
                classify=lambda _candidate, _event: {
                    "action": "finish",
                    "arguments": {},
                    "source": "synthetic checkpoint terminal guard fixture",
                },
            )
        )
        packets = ((32000, b"accepted-prefix"),)
        terminal_runtime = SimpleNamespace(
            fight=fight,
            last_native_delivery=tuple(runtime.last_native_delivery),
            action_id=runtime.action_id,
            expiration_runtime_factory=lambda **_kwargs: self.fail(
                "terminal dead owner must not construct a native marker factory"
            ),
        )
        self.assertEqual(
            presentation.prepare(fight, terminal_runtime, packets), packets
        )


if __name__ == "__main__":
    unittest.main()
