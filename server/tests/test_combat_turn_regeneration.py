import unittest
from types import SimpleNamespace
from unittest.mock import patch
import test_combat_turn_events as turn_tests
from wakfu_server.combat_turn_events import deliver_turn_end, deliver_turn_regeneration
from wakfu_server.combat_server_spell import prepare_server_turn_end
from wakfu_server.fight_checkpoint_store import snapshot


class NativeRegenerationBoundaryTests(unittest.TestCase):
    def test_regeneration_is_distinct_once_only_and_preserves_exact_channels(self):
        fight, dispatcher, seen = turn_tests.OwnedTurnEndTests().fixture()
        deliver_turn_end(dispatcher, actor_id=7)
        deliver_turn_regeneration(dispatcher, actor_id=7)
        self.assertEqual(
            [event.event_ids for event in seen], [(1002,)] * 4 + [(1037,)] * 4
        )
        self.assertEqual(
            [(event.manager_actor_id, event.channel) for event in seen[4:]],
            [(7, 6), (7, 60), (7, 61), (-7, 61)],
        )
        self.assertTrue(all(event.uid is None for event in seen))
        with self.assertRaisesRegex(ValueError, "already delivered"):
            deliver_turn_regeneration(dispatcher, actor_id=7)
        self.assertEqual(len(seen), 8)

    def test_end_suppression_also_suppresses_regeneration_without_refill(self):
        fight, dispatcher, seen = turn_tests.OwnedTurnEndTests().fixture()
        fight.actors[7].native_turn_suppression_bits = 4
        deliver_turn_regeneration(dispatcher, actor_id=7)
        self.assertFalse(seen)
        self.assertTrue(
            fight.native_turn_event_deliveries["1:7:regeneration"]["suppressed"]
        )

    def test_production_end_prepares_both_events_atomically_and_failed_regeneration_rolls_back(
        self,
    ):
        fight, _, _ = turn_tests.OwnedTurnEndTests().fixture()
        original = snapshot(fight)
        seen = []

        def factory(preview, plan):
            def replay(event, **kwargs):
                seen.append(event.event_ids)
                if event.event_ids == (1037,):
                    raise ValueError("unsupported regeneration child")
                return ()

            return (
                SimpleNamespace(
                    native_retention=SimpleNamespace(fight=preview),
                    native_clone_authority=object(),
                    replay_event=replay,
                ),
                [],
            )

        with patch(
            "wakfu_server.combat_server_spell.server_runtime",
            return_value=(factory, None),
        ):
            with self.assertRaisesRegex(ValueError, "regeneration child"):
                prepare_server_turn_end({}, {}, fight, b"", actor_id=7, action_id=1)
        self.assertEqual(seen, [(1002,)] * 4 + [(1037,)])
        self.assertEqual(snapshot(fight), original)
