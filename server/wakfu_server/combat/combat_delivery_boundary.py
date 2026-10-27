"""Preparation contracts for shared publication, recovery and settlement.

These components prepare owned data only. Registry retains lease checks, locks,
state adoption and mailbox routing; storage retains durable reward transactions.
A successful preparation never certifies socket delivery or client rendering.
"""
from copy import copy, deepcopy
from dataclasses import dataclass
import struct


@dataclass(frozen=True)
class PreparedPublication:
    fight: object
    runtime: object
    packets: tuple
    ack: object


@dataclass(frozen=True)
class PreparedReconnect:
    packets: tuple
    fight: object = None
    runtime: object = None
    ack: object = None
    pending_turn_recovered: bool | None = None
    presentation: object = None

    @property
    def recovered_pending_turn(self):
        return (
            self.fight is not None
            if self.pending_turn_recovered is None
            else self.pending_turn_recovered
        )


def native_packets(packets):
    """Own and validate an ordered batch before any state or outbox adoption."""
    packets = tuple(packets)
    if any(
        not isinstance(packet, tuple)
        or len(packet) != 2
        or type(packet[0]) is not int
        or not 0 <= packet[0] <= 0xFFFF
        or not isinstance(packet[1], bytes)
        or len(packet[1]) > 0xFFFFFFFF - 6
        for packet in packets
    ):
        raise ValueError("Combat batch must contain native opcode/body pairs")
    return packets


def accepted_ack(shared, runtime, lease_live):
    """Prepare the next barrier without losing an existing membership fence."""
    pending = getattr(runtime, "awaiting_ack", None)
    barrier = deepcopy(shared.ack)
    if pending is None:
        if barrier.turn is not None:
            raise ValueError("Accepted action cleared a pending shared turn ACK")
        return barrier
    if barrier.turn == pending:
        return barrier
    if barrier.turn is not None:
        raise ValueError("Accepted action replaced a pending shared turn ACK")
    sessions = [
        session
        for account, session in shared.participants.items()
        if account in shared.connected and lease_live(session)
    ]
    barrier.arm(pending, sessions)
    return barrier


def settlement_batches(batches, participants):
    """Validate the entire private roster before publishing any owner result.

    The storage callback has already returned from its durable transaction.
    Invalid encoding cannot be undone here; retry relies on storage idempotency.
    """
    if not isinstance(batches, dict) or set(batches) != set(participants):
        raise ValueError("Shared settlement did not cover its roster")
    return {account: native_packets(packets) for account, packets in batches.items()}


def prepare_reconnect(
    shared,
    session,
    bootstrap_packets,
    *,
    recover_disconnected,
    now_ms,
    prepare_authority=None,
):
    """Stage a native recovery snapshot before the durable lease takeover.

    Ordinary snapshots retain the read-only producer contract. When the last
    owner left with pending ACK, recovery mutates private fight/runtime copies;
    Registry adopts those copies only after persistence succeeds.
    """
    if shared.settlement_ready:
        packets = shared.settlement_batches.get(session.account_id)
        if packets is None:
            raise ValueError("Settled owner packets are unavailable")
        return PreparedReconnect(native_packets(packets))
    from .rift_publication_fence import birth_fence
    from .combat_reconnect_birth_stage import StagedReconnectPackets

    def prepared(packets, *state):
        return PreparedReconnect(
            native_packets(packets),
            *state,
            presentation=(
                packets.presentation
                if isinstance(packets, StagedReconnectPackets)
                else None
            ),
        )

    recover_pending = bool(
        recover_disconnected
        and not shared.connected
        and shared.fight.phase == "active"
        and shared.runtime is not None
        and getattr(shared.runtime, "awaiting_ack", None) is not None
        # A new transport reconstructs ordinary actors in12847 and replays the
        # ORIGINAL12502 below. Its real13510 must complete this birth fence;
        # cancelling the cohort here would strand the deferred native queue.
        and birth_fence(shared.fight) is None
        and not getattr(shared.fight, "native_summon_registrations", {})
    )
    if not recover_pending and prepare_authority is None:
        return prepared(bootstrap_packets(shared.fight, shared, session))
    fight, runtime = deepcopy((shared.fight, shared.runtime))
    ack = deepcopy(shared.ack)
    view = copy(shared)
    view.fight, view.runtime, view.ack = fight, runtime, ack
    if prepare_authority is not None:
        prepare_authority(fight, view, session)
    if recover_pending:
        ack.cancel_for_recovery()
        view.reconnect_turn_end_packets = None
        view.reconnect_remaining_turn_seconds = None
        runtime.recover(session.account_id, struct.pack(">i", fight.id), now_ms=now_ms)
    packets = bootstrap_packets(fight, view, session)
    return prepared(packets, fight, runtime, ack, recover_pending)


def initial_summon_timeline(fight, birth_ids, *, counter=0):
    """Prepare unique INITIAL members; full recovery owns current-cycle slots.

    Additional turns duplicate IDs in the current cycle. Native base order and
    SY progress identify unique members; neither may be replaced by silently
    deduplicating the authoritative current order used in the later recovery.
    """
    from .combat_wire import initial_timeline

    from .combat_timeline_snapshot import counters

    base = getattr(fight, "native_base_turn_order", None)
    base = fight.order if base is None else base
    if len(base) != len(set(base)) or set(base) != {
        int(identity) for identity in counters(fight)
    }:
        raise ValueError("Initial recovery requires unique authoritative base members")
    identities = [identity for identity in base if identity not in birth_ids]
    if type(counter) is not int or not 0 <= counter < 2**31:
        raise ValueError("Invalid actual reconnect witness counter")
    payload = initial_timeline(identities, identities)
    return payload[:2] + struct.pack(">i", counter) + payload[6:]
