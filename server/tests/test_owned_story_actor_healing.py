"""Representative timing/cancellation/once-only bridge for native actor healing."""

from contextlib import nullcontext
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import copy
import sys
import unittest
from unittest.mock import Mock, patch

from wakfu_server import owned_story_actor_healing as healing


class NativeActorHealingTest(unittest.TestCase):
    def test_native_deadline_cancellation_and_single_settlement(self):
        now = datetime(2026, 11, 17, tzinfo=timezone.utc)
        character = dict(
            id=1, account_id=2, map_id=534, instance_id=100, x=-7, y=-1, z=0
        )
        operation = dict(
            consumer="healing",
            action_id=309,
            native_action=dict(aGJ=1, clx=222, getDuration=2000),
            parameters=dict(quest_id=1124, objective_id=2240, step_reference=309),
        )
        identity = dict(
            account_id=2,
            generation=3,
            character_id=1,
            map_id=534,
            instance_id=100,
            position=[-7, -1, 0],
            actor_id=500,
            action_id=309,
            source_sha256="source",
            operation_sha256=healing.controller._digest(operation),
        )
        ticket = dict(identity=identity, due_at=now + timedelta(milliseconds=2000))
        clock = [now]
        store = SimpleNamespace(
            now=lambda: clock[0],
            connection=lambda: nullcontext(object()),
            character=lambda *args: copy.deepcopy(character),
        )
        connection = SimpleNamespace(owned_story_healing=copy.deepcopy(ticket))
        state = SimpleNamespace(
            character=copy.deepcopy(character),
            loaded=True,
            fight=None,
            combat_session=None,
            spectator_session=None,
            environment_ticket=None,
            account_id=2,
            generation=3,
            connection=connection,
        )
        runtime = SimpleNamespace(
            STORE=store,
            flush_positions=Mock(),
            POSITIONS=SimpleNamespace(account_barrier=lambda _: nullcontext()),
        )
        session = SimpleNamespace(
            state=state, runtime=runtime, publish_settled_quest_packets=Mock()
        )
        fake_paid = SimpleNamespace(_leased_owner=Mock())
        fake_mechanics = SimpleNamespace(executor=lambda _: "ordinary-effects")
        row = dict(source_sha256="source")
        with patch.dict(
            sys.modules,
            {
                "wakfu_server.paid_containers": fake_paid,
                "wakfu_server.owned_story_mechanics": fake_mechanics,
            },
        ), patch.object(
            healing, "_selection", return_value=(row, operation, {}, set())
        ), patch.object(
            healing.controller, "_settle", return_value=dict(packets=[(1, b"earned")])
        ) as settle:
            self.assertFalse(healing.poll(session))
            settle.assert_not_called()
            clock[0] = now + timedelta(milliseconds=1999)
            self.assertFalse(healing.poll(session))
            settle.assert_not_called()
            clock[0] = now + timedelta(milliseconds=2000)
            self.assertTrue(healing.poll(session))
            self.assertEqual(settle.call_args.kwargs["reference"], 309)
            self.assertEqual(settle.call_args.kwargs["evidence"]["duration_ms"], 2000)
            self.assertFalse(healing.poll(session))
            self.assertEqual(settle.call_count, 1)
            # A fresh operation canceled by movement cannot reach settlement,
            # even if its native deadline subsequently passes.
            connection.owned_story_healing = copy.deepcopy(ticket)
            state.character["x"] += 1
            self.assertFalse(healing.poll(session))
            self.assertIsNone(connection.owned_story_healing)
            self.assertEqual(settle.call_count, 1)
            session.publish_settled_quest_packets.assert_called_once_with(
                [(1, b"earned")]
            )


if __name__ == "__main__":
    unittest.main()
