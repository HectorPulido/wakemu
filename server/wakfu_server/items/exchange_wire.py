"""Verified native exchange layouts, without ownership or state authorization.

Confirmation13406 carries only an exchange ID, never an offer revision.
The authority must associate confirmation with its published current revision.
Result12997 encodes acceptance0/rejection1 and inviter cancellation4.
"""
import struct


def _identity(value):
    if type(value) is not int or not 0 < value < 2**63:
        raise ValueError("Invalid exchange identity")
    return value


def request(opcode, body):
    if not isinstance(body, bytes):
        raise ValueError("Invalid exchange request body")
    if opcode in (13140, 13406, 12027):
        if len(body) != 8:
            raise ValueError("Invalid exchange identity request length")
        key = "target_id" if opcode == 13140 else "exchange_id"
        return {key: _identity(struct.unpack(">q", body)[0])}
    if opcode in (13037, 12203):
        if len(body) != 18:
            raise ValueError("Invalid exchange item request length")
        uid, exchange_id, quantity = struct.unpack(">qqh", body)
        if quantity < 0 or (opcode == 13037 and quantity == 0):
            raise ValueError("Invalid exchange item quantity")
        return {
            "uid": _identity(uid),
            "exchange_id": _identity(exchange_id),
            "quantity": quantity,
        }
    if opcode == 12781:
        if len(body) != 16:
            raise ValueError("Invalid exchange kamas request length")
        exchange_id, kamas = struct.unpack(">qq", body)
        if kamas < 0:
            raise ValueError("Invalid exchange kamas quantity")
        return {"exchange_id": _identity(exchange_id), "kamas": kamas}
    if opcode == 13113:
        if len(body) < 12:
            raise ValueError("Invalid exchange withdrawal length")
        exchange_id, count = struct.unpack_from(">qi", body)
        if count <= 0 or len(body) != 12 + count * 8:
            raise ValueError("Invalid exchange withdrawal count")
        uids = [_identity(entry[0]) for entry in struct.iter_unpack(">q", body[12:])]
        if len(set(uids)) != count:
            raise ValueError("Duplicate exchange withdrawal identity")
        return {"exchange_id": _identity(exchange_id), "uids": uids}
    if opcode == 12510:
        if len(body) < 12:
            raise ValueError("Invalid bulk exchange offer length")
        exchange_id, count = struct.unpack_from(">qi", body)
        if count <= 0 or count > 128 or len(body) != 12 + count * 8:
            raise ValueError("Invalid bulk exchange offer count")
        uids = [_identity(entry[0]) for entry in struct.iter_unpack(">q", body[12:])]
        if len(set(uids)) != count:
            raise ValueError("Duplicate bulk exchange offer identity")
        return {"exchange_id": _identity(exchange_id), "uids": uids}
    if opcode == 12997:
        if len(body) != 9:
            raise ValueError("Invalid exchange result request length")
        exchange_id, result = struct.unpack(">qB", body)
        return {"exchange_id": _identity(exchange_id), "result": result}
    raise ValueError("Unsupported exchange request opcode")


def proposed(exchange_id, participant_id):
    """cuI12538 consumed by chn: two big-endian i64 identities."""
    return 12538, struct.pack(">qq", _identity(exchange_id), _identity(participant_id))


def invitation_answer(body):
    """daR maps dhI19106 to coD0 and dhJ19851 to coD1."""
    decoded = request(12997, body)
    if decoded["result"] not in (0, 1):
        raise ValueError("Not an exchange invitation answer")
    return {"exchange_id": decoded["exchange_id"], "accepted": decoded["result"] == 0}


def invitation_action(body, *, actor_is_inviter):
    """Decode coD/12997, whose result1 is role-dependent in native UI.

    The installed client sends result1 both when an invitee declines and when
    the inviter cancels the pending dialog. Result4 is another native inviter
    cancellation path. Callers still authorize the resulting action against
    the durable exchange state.
    """
    if type(actor_is_inviter) is not bool:
        raise ValueError("Invalid exchange invitation actor role")
    decoded = request(12997, body)
    result = decoded["result"]
    if result not in (0, 1, 4):
        raise ValueError("Unsupported exchange invitation action")
    if result == 1:
        action = "cancel" if actor_is_inviter else "decline"
    elif result == 4:
        action = "cancel"
    else:
        action = "accept"
    return {
        "exchange_id": decoded["exchange_id"],
        "action": action,
    }


def status(exchange_id, result, participant_id, auxiliary_id):
    """cuH13535 native branches0..4; caller supplies verified identities."""
    if type(result) is not int or not 0 <= result <= 4:
        raise ValueError("Invalid native exchange status")
    return 13535, struct.pack(
        ">qBqq",
        _identity(exchange_id),
        result,
        _identity(participant_id),
        _identity(auxiliary_id),
    )


def ready(exchange_id, actor_id, confirmed):
    """cuO13486: exchange and actor i64, then native boolean byte."""
    if type(confirmed) is not bool:
        raise ValueError("Invalid exchange readiness")
    return 13486, struct.pack(
        ">qq?", _identity(exchange_id), _identity(actor_id), confirmed
    )


def closed(exchange_id, result):
    """cuG12235: exchange i64 and native result branch0..3."""
    if type(result) is not int or not 0 <= result <= 3:
        raise ValueError("Invalid exchange closure result")
    return 12235, struct.pack(">qB", _identity(exchange_id), result)


def _content_status(result):
    # fbW.fe: valid0, inventory full1/2, missing unit3/4, kamas5, other10.
    if type(result) is not int or result not in (0, 1, 2, 3, 4, 5, 10):
        raise ValueError("Invalid exchange content result")
    return result


def cash(exchange_id, actor_id, kamas, *, result=0):
    """cuN13412: two identities, fbW result byte, and signed-long kamas."""
    if type(kamas) is not int or not 0 <= kamas < 2**63:
        raise ValueError("Invalid exchange cash content")
    return 13412, struct.pack(
        ">qqBq",
        _identity(exchange_id),
        _identity(actor_id),
        _content_status(result),
        kamas,
    )


def item(exchange_id, actor_id, unit, quantity, *, removed=False, result=0):
    """cuJ13636/cuK13084: outer quantity then unframed vj item, not protobuf.

    vj carries basic metadata and selected elemental masks. Full ProtoPet
    state is restored by authoritative12471 reconciliation after closure;
    native escrow vj has no ProtoPet field. Eligibility is checked separately.
    """
    from .inventory_items import item_form

    if (
        type(removed) is not bool
        or type(quantity) is not int
        or not 1 <= quantity <= 32767
    ):
        raise ValueError("Invalid exchange item content quantity or operation")
    if not isinstance(unit, dict):
        raise ValueError("Unsupported exchange binary item options")
    return (13084 if removed else 13636), struct.pack(
        ">qqBh",
        _identity(exchange_id),
        _identity(actor_id),
        _content_status(result),
        quantity,
    ) + item_form(unit)
