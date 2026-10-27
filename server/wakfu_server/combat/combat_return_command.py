"""Bound one explicit emergency command to its pending return's exact lease."""
from protocol_codec import decode_body


class PendingEmergencyCommand:
    def __init__(self):
        self.pending = None

    def retain(self, opcode, body, identity):
        if opcode != 12366 or self.pending is not None:
            return False
        try:
            text = decode_body("out", opcode, body)["text"].strip()
        except (ValueError, UnicodeError):
            return False
        if text.lower() not in (
            "!astrub",
            "!exitdungeon",
            "!salirmazmorra",
            "!winfight",
            "!losefight",
        ):
            return False
        self.pending = (tuple(identity), text)
        return True

    def clear(self):
        self.pending = None

    def take(self, identity, *, valid_session):
        pending, self.pending = self.pending, None
        if pending is None or pending[0] != tuple(identity) or not valid_session():
            return None
        return pending[1]
