"""Native13510 is sent by every participant's aUM, not only current actor owner.

Membership snapshot/generation fencing prevents the first client from releasing
other clients' pending presentation. No timeout synthesizes a client ACK.
"""
import struct


class AckBarrier:
    def __init__(self):
        self.turn = None
        self.expected = {}
        self.received = set()

    def arm(self, turn, sessions):
        if self.turn is not None:
            raise ValueError("Combat ACK barrier already pending")
        if type(turn) is not int or not 0 <= turn < 2**31:
            raise ValueError("Invalid native turn ACK counter")
        expected = {session.account_id: session.generation for session in sessions}
        if not expected:
            raise ValueError("Turn ACK requires at least one live participant")
        self.turn = turn
        self.expected = expected
        self.received = set()

    def accept(self, session, body):
        if (
            len(body) != 4
            or self.turn is None
            or struct.unpack(">i", body)[0] != self.turn
        ):
            raise ValueError("Invalid/stale shared turn ACK")
        if self.expected.get(session.account_id) != session.generation:
            raise ValueError("Foreign/stale turn ACK owner")
        self.received.add(session.account_id)
        return self.complete

    @property
    def complete(self):
        return self.turn is not None and self.expected.keys() <= self.received

    def release(self):
        if not self.complete:
            raise ValueError("Participant ACKs still pending")
        turn = self.turn
        self.turn = None
        self.expected = {}
        self.received = set()
        return turn

    def cancel_for_recovery(self):
        """Only explicit native recovery/abort; caller reannounces correct timeline."""
        self.turn = None
        self.expected = {}
        self.received = set()
