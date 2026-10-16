"""Publish native HP dependencies before notifying TOTAL_HP subscribers."""
import struct


def health_dependency_order(payload):
    """Preserve every tA row, applying VIRTUAL_HP before the final HP row.

    Native bkG/bkC derives TOTAL_HP from HP and VIRTUAL_HP. ffh.b writes
    bounds directly, then notifies only when the row's current value changes.
    Publishing HP first can therefore cache a total using the old virtual
    maximum, without a later notification when virtual current stays zero.
    """
    if not isinstance(payload, bytes) or len(payload) < 2:
        raise ValueError("Invalid native characteristic table")
    count = struct.unpack_from(">H", payload)[0]
    if len(payload) != 2 + count * 17:
        raise ValueError("Invalid native characteristic table length")
    rows = [payload[2 + index * 17 : 2 + (index + 1) * 17] for index in range(count)]
    identities = [row[0] for row in rows]
    if 1 not in identities or 92 not in identities:
        return payload
    # Other native row ordering and all raw values remain untouched.
    return (
        payload[:2]
        + b"".join(row for row in rows if row[0] != 1)
        + b"".join(row for row in rows if row[0] == 1)
    )
