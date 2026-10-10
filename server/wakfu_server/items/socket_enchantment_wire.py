"""Native response carriers for socket/enchantment mutation results.

The installed client `cxA.fg` reads status, character actor ID, item UID, a
signed u16 ProtoShard length and lD bytes. `cxy`/`cxz` append their native
QC/QD enum only on the success path.
"""
import struct

from .inventory_shards import initialized_wire_state

_REPLIES = {
    "add_charges": (13703, 0),
    "add_slot": (13703, 1),
    "change_slot_color": (13703, 2),
    "increase_count": (12920, 0),
    "change_colors": (12920, 1),
    "change_order": (12920, 2),
    "apply_sublimation": (13983, None),
    "remove_sublimation": (13793, None),
}
_ERROR_REPLY = {
    12365: 13703,
    13257: 12920,
    12221: 13983,
    12364: 13793,
}


def encode_success(character_id, result):
    if type(character_id) is not int or not 0 < character_id < (1 << 63):
        raise ValueError("Invalid socket response character ID")
    uid = result.get("uid")
    state = initialized_wire_state(bytes(result.get("shard_state", b"")))
    if type(uid) is not int or not 0 < uid < (1 << 63) or len(state) > 32767:
        raise ValueError("Invalid native socket response item")
    try:
        opcode, action = _REPLIES[result["operation"]]
    except (KeyError, TypeError):
        raise ValueError("Unsupported socket mutation response") from None
    body = struct.pack(">BqqH", 0, character_id, uid, len(state)) + state
    if action is not None:
        body += bytes((action,))
    return opcode, body


def encode_failure(request_opcode, status):
    """Encode only the client-confirmed fpE status-only failure path."""
    if request_opcode not in _ERROR_REPLY:
        raise ValueError("Unsupported socket mutation request opcode")
    if type(status) is not int or status not in range(1, 9):
        raise ValueError("Invalid native enchantment failure status")
    return _ERROR_REPLY[request_opcode], bytes((status,))


def packets(character_id, result):
    """Return response plus authoritative inventory and optional wallet refresh."""
    output = [encode_success(character_id, result)]
    inventory = result.get("inventory_packet")
    if (
        not isinstance(inventory, tuple)
        or len(inventory) != 2
        or inventory[0] != 13713
        or not isinstance(inventory[1], bytes)
    ):
        raise ValueError("Missing authoritative socket inventory refresh")
    output.append(inventory)
    cost = result.get("cost_kamas")
    if type(cost) is not int or cost < 0:
        raise ValueError("Invalid socket mutation wallet cost")
    if cost:
        from wakfu_server.wire import account_kamas_update

        balance = result.get("wallet_kamas")
        if type(balance) is not int or balance < 0:
            raise ValueError("Invalid socket mutation wallet balance")
        output.append((12753, account_kamas_update(balance)))
    return output


def bonus_installation_packets(character_id, result):
    """Refresh the native item/bag state after opcode13269 installation.

    The installed client has no dedicated 13269 action-reply enum. The BAGS
    snapshot updates the material reserve. Native 13766 then updates the
    existing item's socket state and refreshes an open enchantment window.
    A configured local fee also refreshes the wallet.
    """
    if type(character_id) is not int or not 0 < character_id < (1 << 63):
        raise ValueError("Invalid socket bonus response character ID")
    inventory = result.get("inventory_packet")
    if (
        not isinstance(inventory, tuple)
        or len(inventory) != 2
        or inventory[0] != 13713
        or not isinstance(inventory[1], bytes)
    ):
        raise ValueError("Missing authoritative socket bonus inventory refresh")
    cost = result.get("cost_kamas")
    if type(cost) is not int or cost < 0:
        raise ValueError("Invalid socket bonus local fee")
    from wakfu_server.items.shard_identification_wire import response

    # chK handles 13766 by updating fpI and refreshing daI's open item window.
    # Send it after BAGS so the snapshot cannot replace the updated item.
    output = [inventory, response(dict(result, status=0))]
    if cost:
        from wakfu_server.wire import account_kamas_update

        balance = result.get("wallet_kamas")
        if type(balance) is not int or balance < 0:
            raise ValueError("Invalid socket bonus wallet balance")
        output.append((12753, account_kamas_update(balance)))
    return output
