"""Answer the native post-snapshot inventory journal query.

13713 installs the owned inventory before the client sends cpP12851. The
12852 response is a deferred mutation journal, not another bag snapshot:
cwQ decodes a notification flag followed by fqe add/remove/quantity entries.
Wakemu publishes inventory changes synchronously through their native mutation
packets and maintains no deferred journal. Its authoritative journal is empty.
Replaying all current items here would duplicate the client's existing items.
"""

import struct

from wakfu_server.inventory_owner import lock_inventory_character


def query(store, account_id, generation, body):
    """Return the empty journal for a selected actor under its real lease.

    The request is valid independently of which inventory/entity packet was
    used during bootstrap. Since the journal has no deferred mutations, this
    response never republishes inventory, equipment, position or statistics.
    """
    if not isinstance(body, bytes) or len(body) != 8:
        raise ValueError("Invalid12851 inventory journal request")
    character_id = struct.unpack(">q", body)[0]
    if character_id <= 0:
        raise ValueError("Invalid inventory journal owner")
    with store.connection() as db:
        lock_inventory_character(store, db, account_id, generation, character_id)
    return 12852, b"\x00"
