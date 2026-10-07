"""Filter participant outbox packets down to native shared fight events.

Combat owner outboxes also carry per-owner bootstrap and settlement packets.
They must never be copied wholesale to a spectator. This allowlist contains the
fight-state and presentation messages produced by the shared combat runtime;
world refreshes, currency, inventory, private reports, and owner bootstrap stay
private to their intended recipient.
"""

from collections import Counter
import struct

PUBLIC_COMBAT_EVENT_OPCODES = frozenset(
    {
        12233,  # start/round transition
        12238,  # native fight end/cleanup
        12304,  # actor removal
        12502,  # end of actor turn
        12514,  # phase/event update
        12588,  # spell animation
        12613,  # retained/running effect application
        12678,  # spell notification
        12727,  # actor death
        12873,  # actor current stats
        13026,  # roster/placement refresh
        13091,  # actor joined
        13337,  # round event
        13477,  # round number
        13482,  # current turn
        13494,  # public actor orientation
        13497,  # native effect application
        13509,  # weapon/melee animation
        13560,  # native effect/state update
        13624,  # combat movement
        13912,  # actor effect snapshot
    }
)


def public_combat_events(batches):
    """Merge recipient copies of one sequence without collapsing repetitions.

    Call this once per shared sequence. Participant outboxes duplicate the same
    broadcast for each owner, while some sequences also contain recipient-only
    bootstrap packets. The longest filtered batch is the ordering anchor; only
    packet multiplicities missing from that anchor are appended.
    """
    variants = []
    for batch in batches:
        public = []
        for packet in batch:
            if (
                isinstance(packet, tuple)
                and len(packet) == 2
                and type(packet[0]) is int
                and packet[0] in PUBLIC_COMBAT_EVENT_OPCODES
                and isinstance(packet[1], bytes)
            ):
                public.append(packet)
        variants.append(tuple(public))
    if not variants:
        return ()
    result = list(max(variants, key=len))
    available = Counter(result)
    for variant in variants:
        observed = Counter()
        for packet in variant:
            observed[packet] += 1
            if observed[packet] > available[packet]:
                result.append(packet)
                available[packet] += 1
    return tuple(result)


def is_normal_finish_packet(packet, fight_id):
    """Recognize normal cvF/12238, excluding the huN=true marker-removal form."""
    if (
        not isinstance(packet, tuple)
        or len(packet) != 2
        or packet[0] != 12238
        or not isinstance(packet[1], bytes)
        or type(fight_id) is not int
        or fight_id <= 0
    ):
        return False
    body = packet[1]
    if len(body) < 16:
        return False
    packet_fight, action_id, target_id = struct.unpack_from(">iii", body)
    if packet_fight != fight_id or action_id <= 0 or target_id != -1 or body[12] != 0:
        return False
    offset = 13
    for _ in range(3):
        count = struct.unpack_from(">b", body, offset)[0]
        offset += 1
        if count < 0 or offset + count * 8 > len(body):
            return False
        offset += count * 8
    return offset == len(body)


def terminal_batch(event_packets, *, fight_id, fallback_packet):
    """Keep one actual native terminal event, appending a fallback if absent.

    Each shared owner receives its own normal result packet with a different
    action sequence. They represent one fight termination, so observers must
    consume exactly one cvF cleanup. External marker removals also use opcode
    12238 but have a shorter huN=true body and are discarded here.
    """
    retained = []
    terminal = None
    for packet in event_packets:
        if isinstance(packet, tuple) and len(packet) == 2 and packet[0] == 12238:
            if terminal is None and is_normal_finish_packet(packet, fight_id):
                terminal = packet
            continue
        retained.append(packet)
    if terminal is None:
        if callable(fallback_packet):
            fallback_packet = fallback_packet()
        if not is_normal_finish_packet(fallback_packet, fight_id):
            raise ValueError("A native normal cvF terminal packet is required")
        terminal = fallback_packet
    return tuple(retained) + (terminal,)
