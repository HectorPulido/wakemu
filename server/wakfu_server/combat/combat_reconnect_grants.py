"""Give owned reconnect grants one constructor, after native ACTION binding.

The final13912 snapshot publishes each retained649 after ACTION. Bootstrap
and the additional evaluated carrier stream must not construct them as well.
Canonical retained payloads and execution flags are never modified.
"""
import struct

from .combat_effect_removal import _identity_fields
from .combat_remote_effects import decode_remote_effects, encode_remote_effects


class ReconnectGrantProjection:
    def __init__(self, carrier_packets):
        self._carriers = {}
        self._projected = set()
        self.other_carriers = []
        for opcode, body in carrier_packets:
            if opcode != 12613 or len(body) < 19:
                self.other_carriers.append((opcode, body))
                continue
            effect_class, size = struct.unpack_from(">ih", body, 13)
            if effect_class != 649:
                self.other_carriers.append((opcode, body))
                continue
            if size <= 0 or len(body) != 19 + size or body[12] != 0:
                raise ValueError("Invalid evaluated reconnect grant carrier")
            payload = body[19:]
            fields = _identity_fields(payload)
            uid = fields.get(1)
            if type(uid) is not int or uid <= 0 or uid in self._carriers:
                raise ValueError("Duplicate or missing reconnect grant UID")
            self._carriers[uid] = payload

    def effects(self, actor_id, effects):
        retained = []
        for record in decode_remote_effects(effects):
            if record.effect_class != 649:
                retained.append(record)
                continue
            fields = _identity_fields(record.payload)
            uid = fields.get(1)
            target = fields.get(7)
            if isinstance(target, int) and target >= 1 << 63:
                target -= 1 << 64
            if (
                target != actor_id
                or uid in self._projected
                or self._carriers.get(uid) != record.payload
            ):
                raise ValueError("Reconnect grant lacks its exact retained carrier")
            self._projected.add(uid)
        return encode_remote_effects(retained)

    def verify_complete(self):
        if self._projected != set(self._carriers):
            raise ValueError("Reconnect grant projection omitted a live carrier")
