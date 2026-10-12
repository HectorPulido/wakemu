"""Qf.clear new HashSet(bfT.keySet()) order for qualified non-tree buckets.

LinkedHashMap supplies insertion order. A Java HashMap tree bin can reorder its
root; that domain is rejected rather than silently borrowing Python set order.
"""
import struct


def qf_clear_order(manager_uid_order):
    values = tuple(manager_uid_order)
    if len(values) != len(set(values)) or any(
        type(value) is not int or not -(1 << 63) <= value < (1 << 63)
        for value in values
    ):
        raise ValueError("Missing exact native LinkedHashMap UID population")
    if not values:
        return ()
    quotient = struct.unpack(">f", struct.pack(">f", len(values) / 0.75))[0]
    requested = max(int(quotient) + 1, 16)
    capacity = 1
    while capacity < requested:
        capacity *= 2
    buckets = {}
    for value in values:
        unsigned = value & ((1 << 64) - 1)
        h = ((unsigned >> 32) ^ unsigned) & 0xFFFFFFFF
        spread = h ^ (h >> 16)
        bucket = spread & (capacity - 1)
        chain = buckets.setdefault(bucket, [])
        chain.append(value)
        if len(chain) > 8:
            raise ValueError(
                "Native HashSet tree/resize collision domain is not qualified"
            )
    return tuple(value for bucket in sorted(buckets) for value in buckets[bucket])
