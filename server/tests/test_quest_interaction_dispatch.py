import unittest
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import Mock

from wakfu_server.application.quest_interaction_dispatch import settle_interaction


class QuestInteractionDispatchTests(unittest.TestCase):
    def make_context(self, events):
        @contextmanager
        def account_barrier(account_id):
            events.append(("barrier_enter", account_id))
            try:
                yield
            finally:
                events.append(("barrier_exit", account_id))

        character = {"id": 42, "account_id": 7, "quest_items": []}
        runtime = SimpleNamespace(
            POSITIONS=SimpleNamespace(account_barrier=account_barrier),
            STORE=object(),
            flush_positions=Mock(
                side_effect=lambda **kwargs: events.append(("flush", kwargs))
            ),
            record=Mock(side_effect=lambda **kwargs: events.append(("record", kwargs))),
        )
        state = SimpleNamespace(
            account_id=7,
            generation="lease-1",
            character=character,
            body=b"interaction",
            loaded=True,
            environment_ticket=None,
        )
        session = SimpleNamespace(
            state=state,
            runtime=runtime,
            environment_blocked=Mock(return_value=False),
            publish_settled_quest_packets=Mock(
                side_effect=lambda packets: events.append(("publish", packets))
            ),
        )
        return session, runtime, state

    def test_handled_result_refreshes_state_and_publishes_only_after_flush(self):
        events = []
        session, runtime, state = self.make_context(events)
        original_character = state.character
        refreshed = {"id": 42, "account_id": 7, "quest_items": [18689]}
        result = {
            "applied": False,
            "handled": True,
            "character": refreshed,
            "packets": [b"quest", b"inventory"],
            "completed": [2048],
        }

        def handler(store, account, generation, character, body, **kwargs):
            events.append(
                ("handler", store, account, generation, character, body, kwargs)
            )
            return result

        handled = settle_interaction(
            session, handler, event="quest_pickup", object_id=23033
        )

        self.assertTrue(handled)
        self.assertIs(refreshed, state.character)
        self.assertEqual(
            ["barrier_enter", "flush", "handler", "publish", "record", "barrier_exit"],
            [event[0] for event in events],
        )
        self.assertEqual([b"quest", b"inventory"], events[3][1])
        session.publish_settled_quest_packets.assert_called_once_with(result["packets"])
        runtime.record.assert_called_once_with(
            event="quest_pickup",
            actor_id=42,
            object_id=23033,
            completed=[2048],
        )
        runtime.flush_positions.assert_called_once_with(
            account_id=7, generation="lease-1", character_id=42
        )
        handler_args = events[2][1:]
        self.assertIs(original_character, handler_args[3])
        self.assertEqual({"loaded": True, "blocked": False}, handler_args[5])

    def test_unhandled_result_emits_nothing(self):
        events = []
        session, runtime, state = self.make_context(events)
        handler = Mock(return_value={"applied": False, "handled": False})

        handled = settle_interaction(
            session, handler, event="quest_pickup", object_id=1
        )

        self.assertFalse(handled)
        self.assertEqual(
            ["barrier_enter", "flush", "barrier_exit"],
            [event[0] for event in events],
        )
        self.assertEqual(
            {"id": 42, "account_id": 7, "quest_items": []}, state.character
        )
        session.publish_settled_quest_packets.assert_not_called()
        runtime.record.assert_not_called()

    def test_producer_exception_emits_nothing(self):
        events = []
        session, runtime, _ = self.make_context(events)
        handler = Mock(side_effect=RuntimeError("producer failed"))

        with self.assertRaisesRegex(RuntimeError, "producer failed"):
            settle_interaction(session, handler, event="quest_pickup", object_id=1)

        self.assertEqual(
            ["barrier_enter", "flush", "barrier_exit"],
            [event[0] for event in events],
        )
        session.publish_settled_quest_packets.assert_not_called()
        runtime.record.assert_not_called()


if __name__ == "__main__":
    unittest.main()
