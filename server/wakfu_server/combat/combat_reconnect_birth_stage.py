"""Recipient-local native birth recovery behind an actual end-turn witness.

A creation group closes asynchronously. Its original12502/aUM is the native
completion witness;13510 here never invents or advances an authoritative turn.
All later public batches remain ordered behind this private presentation.
"""
from collections import deque
from dataclasses import dataclass, field
import struct
import time


MAX_BUFFER_BYTES = 8 * 1024 * 1024
MAX_BUFFER_BATCHES = 256
MAX_RECOVERY_SECONDS = 120


@dataclass(frozen=True)
class BirthPresentation:
    counter: int
    actor_ids: tuple
    resume_packets: tuple
    marker_packets: tuple = ()
    canonical_marker: bool = False

    def __post_init__(self):
        if (
            type(self.counter) is not int
            or not 0 < self.counter < 2**31
            or not self.actor_ids
            or len(self.actor_ids) != len(set(self.actor_ids))
            or any(
                type(identity) is not int or identity == 0
                for identity in self.actor_ids
            )
            or type(self.canonical_marker) is not bool
        ):
            raise ValueError("Invalid reconnect birth presentation")
        from .combat_delivery_boundary import native_packets

        native_packets(self.resume_packets)
        native_packets(self.marker_packets)
        if any(opcode not in (12502, 13420) for opcode, _ in self.marker_packets):
            raise ValueError(
                "Reconnect witness requires original end-turn presentation"
            )
        if self.marker_packets and not any(
            opcode == 12502 for opcode, _ in self.marker_packets
        ):
            raise ValueError("Reconnect witness lacks its native end-turn action")
        if any(opcode == 12502 for opcode, _ in self.resume_packets):
            raise ValueError("Reconnect continuation cannot end an authoritative turn")


class StagedReconnectPackets(tuple):
    """A native packet tuple whose private continuation survives prefixing."""

    def __new__(cls, packets, presentation):
        if not isinstance(presentation, BirthPresentation):
            raise ValueError("Missing native birth presentation contract")
        value = super().__new__(cls, packets)
        value.presentation = presentation
        return value

    def prefixed(self, packets):
        return type(self)(tuple(packets) + tuple(self), self.presentation)


@dataclass
class PendingBirthPresentation:
    session: object
    presentation: BirthPresentation
    marker_sent: bool
    batches: deque = field(default_factory=deque)
    buffered_bytes: int = 0
    deadline: float = field(
        default_factory=lambda: time.monotonic() + MAX_RECOVERY_SECONDS
    )
    overflowed: bool = False

    @classmethod
    def bind(cls, session, presentation):
        if not getattr(session, "generation", None):
            raise ValueError("Reconnect birth presentation lacks its session lease")
        return cls(session, presentation, bool(presentation.marker_packets))

    def witness(self, session, body):
        if self.session != session:
            raise ValueError("Foreign or stale reconnect birth witness")
        return (
            self.marker_sent
            and isinstance(body, bytes)
            and len(body) == 4
            and struct.unpack(">i", body)[0] == self.presentation.counter
        )

    def check_transport(self):
        if self.overflowed or time.monotonic() >= self.deadline:
            raise ConnectionError(
                "Native combat recovery exceeded its transport buffer"
            )

    def buffer(self, batch, *, awaiting_ack, fight_id):
        """Retain every event; expose only a real first end-turn if needed."""
        size = sum(len(body) + 6 for _, body in batch.packets)
        if (
            self.overflowed
            or len(self.batches) >= MAX_BUFFER_BATCHES
            or self.buffered_bytes + size > MAX_BUFFER_BYTES
            or time.monotonic() >= self.deadline
        ):
            self.overflowed = True
            self.batches.clear()
            self.buffered_bytes = 0
            return ()
        self.batches.append(batch)
        self.buffered_bytes += size
        if self.marker_sent:
            return ()
        endings = tuple(packet for packet in batch.packets if packet[0] == 12502)
        if not endings:
            return ()
        if awaiting_ack != self.presentation.counter:
            # A private recovery must never roll back another owner's accepted
            # publication. The home transport will close through its own lease.
            self.overflowed = True
            self.batches.clear()
            self.buffered_bytes = 0
            return ()
        self.marker_sent = True
        return endings + ((13420, struct.pack(">i", fight_id)),)
