"""Rejected native board requests preserve the authenticated session."""

from contextlib import nullcontext
from types import SimpleNamespace
import struct
import unittest
from unittest.mock import Mock, patch

from wakfu_server.application import mercenary_board_dispatch
from wakfu_server.application.dispatch_result import DispatchResult


class MercenaryBoardDispatchTests(unittest.TestCase):
    def test_duplicate_selection_sends_feedback_without_an_ambient_state_callback(self):
        state = SimpleNamespace(
            opcode=12864,
            body=struct.pack(">iqB", 2140, -1, 1),
            account_id=314,
            generation="owned-generation",
            character={"id": 388},
            connection=object(),
            service="world",
            environment_ticket=None,
        )
        runtime = SimpleNamespace(
            POSITIONS=SimpleNamespace(account_barrier=lambda _: nullcontext()),
            STORE=object(),
            flush_positions=Mock(),
            record=Mock(),
            send=Mock(),
        )
        session = SimpleNamespace(
            state=state,
            runtime=runtime,
            environment_blocked=lambda: False,
            publish_settled_quest_packets=Mock(),
        )
        with patch(
            "wakfu_server.mercenary_boards.select",
            side_effect=ValueError("Mercenary selection was not offered to this owner"),
        ):
            result = mercenary_board_dispatch.dispatch(session)
        self.assertIs(result, DispatchResult.CONTINUE)
        runtime.send.assert_called_once()
        args = runtime.send.call_args.args
        self.assertEqual(args[:3], (state.connection, "world", 349))
        self.assertIn(b"Reopen the mercenary board", args[3])
        self.assertIsNone(state.mercenary_board_offer)
        session.publish_settled_quest_packets.assert_not_called()


if __name__ == "__main__":
    unittest.main()
