"""eWR/fap.RESISTANCE_CAP and eWW.a ordered refilling of owned runners.

The cap is on same action/status-zero running values, not total resistance.
Removal walks Qf's insertion order. Requested values remain prepercent values.
"""
from .combat_effect_removal import _identity_fields, _read_varint
from .combat_effects import _integer


def i32(value):
    return (value + (1 << 31)) % (1 << 32) - (1 << 31)


def _number(value):
    if type(value) is not int or not -(1 << 31) <= value < (1 << 31):
        raise ValueError("Unknown native resistance runner amount")
    return value


def requested_from_payload(payload):
    messages = {}
    _identity_fields(payload, messages=messages)
    if 8 not in messages:
        raise ValueError("Missing owned resistance request AdditionalDatas")
    fields = _identity_fields(messages[8], integer_fields=(25,))
    if 25 not in fields:
        raise ValueError("Missing owned resistance prepercent request")
    return i32(fields[25])


def replace_value(payload, value):
    """Replace exactly field4; retain clocks, UID and AdditionalDatas unchanged."""
    _number(value)
    result = bytearray()
    offset = 0
    found = False
    while offset < len(payload):
        start = offset
        tag, offset = _read_varint(payload, offset)
        field, wire = tag >> 3, tag & 7
        if wire == 0:
            _, offset = _read_varint(payload, offset)
        elif wire == 2:
            length, offset = _read_varint(payload, offset)
            offset += length
        elif wire in (1, 5):
            offset += 8 if wire == 1 else 4
        else:
            raise ValueError("Unsupported owned running protobuf wire")
        if not field or offset > len(payload):
            raise ValueError("Invalid owned running protobuf")
        if field == 4:
            if found or wire != 0:
                raise ValueError("Invalid owned running value field")
            found = True
            result.extend(_integer(4, value))
        else:
            result.extend(payload[start:offset])
    if not found:
        raise ValueError("Missing owned running value")
    return bytes(result)


def same_action_rows(owned, *, target_id, effect_class, excluding_uid=None):
    """Owned dict has native Qf/LinkedHashMap application order.

    eWR.d always installs cYh=0. Other families with the same action are not
    silently counted: the native downcast in eWR.C likewise requires eWR.
    """
    if not isinstance(owned, dict):
        raise ValueError("Missing ordered owned resistance manager")
    result = []
    for uid, row in owned.items():
        if (
            uid == excluding_uid
            or row.get("target_id") != target_id
            or row.get("effect_class") != effect_class
        ):
            continue
        if row.get("family") != "eWR":
            raise ValueError("Invalid same-action native resistance runner")
        status = row.get("execution_status")
        if status not in (None, 0):
            continue
        _number(row.get("actual"))
        result.append((uid, row))
    return result


def capped_request(requested, rows):
    """eWR.C after eWW.C, before percentage conversion and PA.oo."""
    amount = _number(requested)
    total = amount
    for _, row in rows:
        total = i32(total + _number(row.get("actual")))
    return max(0, i32(amount - i32(total - 200))) if total >= 200 else amount


def refill(current, minimum, maximum, frozen, rows):
    """eWW.a(PA,200); plan updates before committing any owned row.

    Native aSg grows by the allocated amount even when PA.oo clamps/freezes.
    No replacement application packet is emitted: client bbR does this too.
    """
    for v in (current, minimum, maximum):
        _number(v)
    if not minimum <= current <= maximum or type(frozen) is not bool:
        raise ValueError("Missing resistance resource bounds/mutability")
    absolute = current if current == -(1 << 31) else abs(current)
    capacity = i32(200 - absolute)
    updates = []
    if capacity <= 0:
        return current, updates
    for uid, row in rows:
        if capacity <= 0:
            break
        actual = _number(row["actual"])
        payload = bytes.fromhex(row["payload"])
        requested = requested_from_payload(payload)
        if requested == actual:
            continue
        amount = min(capacity, i32(requested - actual))
        current = current if frozen else max(minimum, min(maximum, current - amount))
        capacity = i32(capacity - amount)
        new_actual = i32(actual + amount)
        updates.append((uid, new_actual, replace_value(payload, new_actual)))
    return current, updates
