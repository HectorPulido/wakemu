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


def terminal_presentation_has_recipients(shared, *, replacing=None):
    """Only exact current world-return tokens exclude a connected recipient.

    Registry has already fenced the replaced session's old lease before
    supplying replacing; that transport cannot own an old scene any longer.
    """
    from .combat_shared import PendingWorldRecovery

    for account in shared.connected:
        owner = shared.participants.get(account)
        if (
            replacing is not None
            and owner is not None
            and account == replacing.account_id
            and owner.generation != replacing.generation
        ):
            continue
        token = shared.pending_world_recoveries.get(account)
        if not (
            type(token) is PendingWorldRecovery
            and token.session == owner
            and token.fight_id == shared.fight.id
        ):
            return True
    return False


def prepare_reconnect(
    shared,
    session,
    bootstrap_packets,
    *,
    recover_disconnected,
    now_ms,
    prepare_authority=None,
    fresh_world=False,
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

    retire_terminal = False
    if fresh_world:
        from .combat_runtime_messages import RuntimeMessages

        if (
            shared.fight.phase != "finished"
            or shared.fight.winner not in (0, 1)
            or getattr(shared, "is_duel", False)
            or getattr(shared.runtime, "abandon_owner", None) is not None
        ):
            raise ValueError("Terminal presentation retirement requires resolved PvE")
        # Fresh-world peers never received the old scene. Preserve every
        # genuine scene recipient, including its outstanding real ACK.
        if not terminal_presentation_has_recipients(shared, replacing=session):
            counter = getattr(shared.runtime, "awaiting_ack", None)
            barrier = shared.ack
            if counter != barrier.turn:
                raise ValueError(
                    "Terminal recovery has inconsistent native ACK boundary"
                )
            if counter is not None:
                if (
                    type(shared.runtime) is not RuntimeMessages
                    or type(counter) is not int
                    or type(barrier.turn) is not int
                    or shared.runtime.fight is not shared.fight
                    or not barrier.expected
                    or not barrier.received <= barrier.expected.keys()
                    or any(
                        type(owner) is not int
                        or owner not in shared.participants
                        or shared.participants[owner].generation != generation
                        for owner, generation in barrier.expected.items()
                    )
                ):
                    raise ValueError(
                        "Terminal recovery lacks exact presentation owners"
                    )
                retire_terminal = True

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
    if not recover_pending and not retire_terminal and prepare_authority is None:
        return prepared(bootstrap_packets(shared.fight, shared, session))
    fight, runtime = deepcopy((shared.fight, shared.runtime))
    ack = deepcopy(shared.ack)
    view = copy(shared)
    view.fight, view.runtime, view.ack = fight, runtime, ack
    if prepare_authority is not None:
        prepare_authority(fight, view, session)
    if retire_terminal:
        # This is cancellation of an orphaned transport presentation, never a
        # client acknowledgement or a gameplay transition. Registry adopts the
        # private copies only after the durable replacement lease commits.
        if not runtime._close_terminal_turn():
            raise ValueError("Terminal recovery changed its resolved phase")
        ack.cancel_for_recovery()
    if recover_pending:
        ack.cancel_for_recovery()
        view.reconnect_turn_end_packets = None
        view.reconnect_remaining_turn_seconds = None
        runtime.recover(session.account_id, struct.pack(">i", fight.id), now_ms=now_ms)
    packets = bootstrap_packets(fight, view, session)
    return prepared(packets, fight, runtime, ack, recover_pending or retire_terminal)


def initial_summon_timeline(fight, birth_ids, *, counter=0, witness_actor=None):
    """Prepare unique members and an optional original end-turn witness.

    A known original12502 must end an ON member, never INITIAL's -1 slot.
    This recipient-only presentation does not execute a server turn callback;
    the full recovery still owns every authoritative current-cycle slot.

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
    payload = payload[:2] + struct.pack(">i", counter) + payload[6:]
    if witness_actor is None:
        return payload
    if type(witness_actor) is not int or witness_actor not in identities:
        raise ValueError("Reconnect turn-end witness is not an initial member")
    # SU header15, two SX count+ID arrays, then SY count+(ID,progress).
    # Tc's following signed cursor must identify the actual original marker.
    cursor_offset = 15 + 2 * (1 + 8 * len(identities)) + 1 + 10 * len(identities)
    return (
        payload[:6]
        + b"\x01"  # Native ON_FIGHTER_TURN, before the original end witness.
        + payload[7:cursor_offset]
        + struct.pack(">b", identities.index(witness_actor))
        + payload[cursor_offset + 1 :]
    )
