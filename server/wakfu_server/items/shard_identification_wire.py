"""Native identification response for existing inventory item UIDs."""
import struct

from wakfu_server.inventory_shards import initialized_wire_state


def response(result):
    uid = result.get("uid")
    status = result.get("status")
    if type(uid) is not int or not 0 < uid < 2**63:
        raise ValueError("Invalid identification result UID")
    if type(status) is not int or status not in (0, 2):
        raise ValueError("Unsupported identification result status")
    elements = result.get("elements", b"")
    if not isinstance(elements, bytes) or len(elements) not in (0, 2):
        raise ValueError("Invalid identification elemental state")
    if any(value & ~30 for value in elements):
        raise ValueError("Invalid identification elemental mask")
    shard = result.get("shard_state")
    if shard is None:
        if status == 0:
            raise ValueError("Successful identification lacks shard state")
        shard = b""
    else:
        shard = initialized_wire_state(shard)
    return (
        13766,
        struct.pack(">iqBI", status, uid, 0, len(elements))
        + elements
        + struct.pack(">I", len(shard))
        + shard,
    )
