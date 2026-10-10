"""Native client request for feeding an owned pet/mount item.

The client ``crX`` message uses opcode 12767 and serializes pet item UID, food
UID, and selected quantity as two signed 64-bit integers followed by a signed
32-bit integer, all big-endian. The outer protocol wrapper is handled by the
transport; these helpers encode/decode only the fixed-width message body.
"""
import struct


_BODY = struct.Struct(">qqi")
_MAX_UID = (1 << 63) - 1
_MAX_QUANTITY = (1 << 15) - 1
OPCODE = 12767


def _uid(value):
    if type(value) is not int or not 1 <= value <= _MAX_UID:
        raise ValueError("Invalid feeding item UID")
    return value


def _quantity(value):
    # The initiating UI action carries a Java short count, though crX writes
    # the selected count as an int32.
    if type(value) is not int or not 1 <= value <= _MAX_QUANTITY:
        raise ValueError("Invalid feeding quantity")
    return value


def encode_request(food_uid, pet_uid, quantity):
    """Return the exact 20-byte opcode-12767 payload."""
    return _BODY.pack(_uid(pet_uid), _uid(food_uid), _quantity(quantity))


def decode_request(payload):
    """Decode a complete opcode-12767 payload; reject truncation/trailing data."""
    if type(payload) is not bytes or len(payload) != _BODY.size:
        raise ValueError("Invalid feeding request body")
    pet_uid, food_uid, quantity = _BODY.unpack(payload)
    return {
        "food_uid": _uid(food_uid),
        "pet_uid": _uid(pet_uid),
        "quantity": _quantity(quantity),
    }


def remove_delta(uid, quantity):
    """Native cwZ/12470 signed quantity delta for a stack removal."""
    _uid(uid)
    if type(quantity) is not int or not 1 <= quantity <= _MAX_QUANTITY:
        raise ValueError("Invalid feeding removal quantity")
    return 12470, struct.pack(">qh", uid, -quantity)


def refresh_packets(food, pet, quantity):
    """Compose the tested inventory model refresh sequence.

    The item model rejects duplicate UIDs, so the pet unit is removed before
    reinsertion with its same UID/slot and updated ProtoPet. This is a native
    model-supported composition, not a dedicated update opcode; callers must
    not replay additive packets blindly after partial transport delivery.
    """
    _uid(food["uid"])
    _uid(pet["uid"])
    if food["uid"] == pet["uid"]:
        raise ValueError("Food and pet UIDs must differ")
    if type(pet.get("quantity")) is not int or pet["quantity"] != 1:
        raise ValueError("Refreshed pet must be an unstacked unit")
    from .inventory_items import insertion

    return [
        remove_delta(food["uid"], quantity),
        remove_delta(pet["uid"], 1),
        insertion(pet),
    ]


# Kept as a descriptive alias for the domain service.
publication_packets = refresh_packets
