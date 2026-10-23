"""Native environmental result display, independently of reward settlement."""

import struct


def _signed(value, bits, field):
    if type(value) is not int or not -(1 << (bits - 1)) <= value < 1 << (bits - 1):
        raise ValueError("Invalid native environmental " + field)
    return value


def result_packet(
    *, challenge_id, secondary_id, name, result_parameter, rank_minus_one, result_value
):
    """Encode cAL13263 without inventing ranking or payout policy.

    The original decoder reads a signed byte UTF-8 length and signed short
    rank; its consumer displays rank + 1. A zero length decodes as null on a
    fresh message. Secondary identity is decoded but is not a consumer fence.
    Original cio passes result_value to bhE.CK: it selects the primary reward
    list index, not an arbitrary score. Raw codec bounds are not UI policy.
    Its rank + 1 is cast back to short; raw32767 wraps to negative32768.
    """
    if name is not None and type(name) is not str:
        raise ValueError("Invalid native environmental result name")
    encoded = b"" if name is None else name.encode("utf-8")
    if len(encoded) > 127:
        raise ValueError("Native environmental result name exceeds 127 UTF-8 bytes")
    return 13263, (
        struct.pack(
            ">iib",
            _signed(challenge_id, 32, "challenge id"),
            _signed(secondary_id, 32, "secondary id"),
            len(encoded),
        )
        + encoded
        + struct.pack(
            ">ihi",
            _signed(result_parameter, 32, "result parameter"),
            _signed(rank_minus_one, 16, "rank minus one"),
            _signed(result_value, 32, "result value"),
        )
    )
