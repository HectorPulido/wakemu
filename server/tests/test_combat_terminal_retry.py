import unittest
from types import SimpleNamespace
from wakfu_server.combat_terminal_retry import pending_terminal_settlement


class TerminalRetryTests(unittest.TestCase):
    def state(self, **changes):
        shared = SimpleNamespace(
            fight=SimpleNamespace(phase="finished", winner=0),
            runtime=SimpleNamespace(awaiting_ack=None),
            settlement_ready=False,
        )
        for key, value in changes.items():
            setattr(shared, key, value)
        return shared

    def test_finished_pve_without_ack_retries(self):
        self.assertTrue(pending_terminal_settlement(self.state()))

    def test_committed_and_pending_ack_do_not_retry(self):
        self.assertFalse(pending_terminal_settlement(self.state(settlement_ready=True)))
        self.assertFalse(
            pending_terminal_settlement(
                self.state(runtime=SimpleNamespace(awaiting_ack=42))
            )
        )

    def test_abandon_and_unresolved_do_not_retry(self):
        self.assertFalse(
            pending_terminal_settlement(
                self.state(
                    runtime=SimpleNamespace(awaiting_ack=None, abandon_owner=(2, 13))
                )
            )
        )
        self.assertFalse(
            pending_terminal_settlement(
                self.state(fight=SimpleNamespace(phase="active", winner=None))
            )
        )
        self.assertFalse(pending_terminal_settlement(None))
