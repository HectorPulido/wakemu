"""Application domain helpers extracted from the World bootstrap."""

import socket
import struct


class NetworkDelivery:
    def __init__(self, runtime):
        self.runtime = runtime

    def receive(self, connection, count, on_idle=None):
        data = bytearray()
        while len(data) < count:
            try:
                objectives_updates = getattr(connection, "objectives_updates", None)
                if objectives_updates is not None and not connection.pending():
                    import select

                    readable, _, _ = select.select(
                        (connection, objectives_updates.reader), (), (), 1.0
                    )
                    if objectives_updates.reader in readable:
                        objectives_updates.drain()
                        if on_idle is not None and not on_idle():
                            raise ValueError("Session expired or replaced")
                    if connection not in readable:
                        if not readable and on_idle is not None and not on_idle():
                            raise ValueError("Session expired or replaced")
                        continue
                chunk = connection.recv(count - len(data))
            except socket.timeout:
                if on_idle is None or not on_idle():
                    raise ValueError("Session expired or replaced")
                continue
            if not chunk:
                raise EOFError()
            data.extend(chunk)
        return bytes(data)

    def record_combat_wire_effect(self, connection, service, opcode, body):
        """Optionally log safe identity fields for outgoing native 12613 packets."""
        if not self.runtime.COMBAT_WIRE_TRACE or service != "world" or opcode != 12613:
            return
        try:
            from wakfu_server.combat_wire_diagnostics import (
                effect_application_metadata,
            )

            metadata = effect_application_metadata(opcode, body)
            if metadata is None:
                return
            self.runtime.record(
                event="combat_effect_wire",
                service=service,
                direction="out",
                target_connection_id=getattr(connection, "trace_id", None),
                **metadata,
            )
        except Exception:
            # Diagnostics run after the successful write and must never affect it.
            return

    def publish_item_spell_updates(self, connection, service, opcode, body):
        """Remember delivered native item spell additions."""
        if service != "world":
            return
        if opcode == 12503 and len(body) >= 8 and (len(body) - 8) % 14 == 0:
            seen = getattr(connection, "item_spell_uids", None)
            if seen is not None:
                for offset in range(8, len(body), 14):
                    seen.add(struct.unpack_from(">q", body, offset + 4)[0])
        if opcode == 13873 and len(body) >= 12 and body[:8] == struct.pack(">II", 1, 4):
            callback = getattr(connection, "account_item_spell_update", None)
            if callback is not None:
                callback()

    def send(self, connection, service, opcode, body):
        if getattr(connection, "is_bot_peer", False):
            return
        write = lambda: connection.sendall(
            struct.pack(">IH", 6 + len(body), opcode) + body
        )
        if service == "world" and self.runtime.NATIVE_PLANTING_BONUS:
            self.runtime.PLANTING_BONUSES.deliver(connection, ((opcode, body),), write)
        else:
            write()
        self.runtime.record(
            service=service,
            direction="out",
            opcode=opcode,
            bytes=len(body),
            target_connection_id=getattr(connection, "trace_id", None),
        )
        self.runtime.record_combat_wire_effect(connection, service, opcode, body)
        self.runtime.publish_item_spell_updates(connection, service, opcode, body)

    def send_batch(self, connection, service, packets):
        if getattr(connection, "is_bot_peer", False):
            return
        packets = tuple(packets)
        if not packets:
            return
        frames = []
        for opcode, body in packets:
            if type(opcode) is not int or not 0 <= opcode <= 0xFFFF:
                raise ValueError("Invalid pushed packet opcode")
            if not isinstance(body, bytes) or len(body) > 327670 - 6:
                raise ValueError("Invalid pushed packet body")
            frames.append(struct.pack(">IH", 6 + len(body), opcode) + body)
        # Connection.sendall holds one write lock for the entire ordered batch.
        write = lambda: connection.sendall(b"".join(frames))
        if service == "world" and self.runtime.NATIVE_PLANTING_BONUS:
            self.runtime.PLANTING_BONUSES.deliver(connection, packets, write)
        else:
            write()
        for opcode, body in packets:
            self.runtime.record(
                service=service,
                direction="out",
                opcode=opcode,
                bytes=len(body),
                target_connection_id=getattr(connection, "trace_id", None),
            )
            self.runtime.record_combat_wire_effect(connection, service, opcode, body)
            self.runtime.publish_item_spell_updates(connection, service, opcode, body)
