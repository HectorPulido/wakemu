"""Native eZz/eZA partial tackle presentation from committed movement receipts.

These transient runners are the original eZz.b/eZA.c(PN, fyQ, PV) products,
not spell losses. Their client completion subtracts resources, so callers must
place them before the authoritative post-movement characteristic snapshots.
"""
import struct

from .combat_effects import _integer, _varint


def _message(field, payload):
    return _varint((field << 3) | 2) + _varint(len(payload)) + payload


def tackle_loss_messages(fight_id, action_id, actor_id, event):
    """Encode only the paid tackle surcharge, excluding the ordinary step MP."""
    if not isinstance(event, dict):
        raise ValueError("Missing committed movement event")
    losses = (event.get("tackle_ap", 0), event.get("tackle_mp", 0))
    if any(type(value) is not int or not 0 <= value < (1 << 31) for value in losses):
        raise ValueError("Invalid committed tackle resource loss")
    if (
        type(actor_id) is not int
        or not -(1 << 63) <= actor_id < (1 << 63)
        or not actor_id
    ):
        raise ValueError("Missing tackle movement actor identity")
    # The factories leave UID, base UID and PK at the native transient -1.
    # eZR.QH serializes fresh timing/status defaults, not a retained spell.
    timing = _integer(1, 0) + _integer(2, -1) + _integer(3, 0)
    extra = (
        _integer(1, 0)
        + _integer(2, -1)
        + _message(3, timing)
        + _integer(4, -1)
        + _integer(5, 0)
    )
    position = _integer(1, 0) + _integer(2, 0) + _integer(3, 0)
    packets = []
    for family, amount in zip((1077, 1078), losses):
        if not amount:
            continue
        payload = (
            _integer(1, -1)
            + _integer(2, -1)
            + _integer(3, -1)
            + _integer(4, amount)
            + _message(5, position)
            + _integer(7, actor_id)
            + _message(11, extra)
        )
        packets.append(
            (
                12613,
                struct.pack(">iiiBih", fight_id, action_id, -1, 0, family, len(payload))
                + payload,
            )
        )
    return packets
