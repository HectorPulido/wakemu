"""Public neutral bootstrap bodies from original native codec layouts.

These are fixture policies, not captured accounts or production entitlements.
No source capture, client archive, database or network is needed at runtime.
"""
import struct
import unicodedata


def _identity(value, label):
    if type(value) is not int or not 0 < value < (1 << 63):
        raise ValueError(f"Invalid {label}")
    return value


def _name(value):
    if (
        type(value) is not str
        or not value
        or any(unicodedata.category(char).startswith("C") for char in value)
    ):
        raise ValueError("Invalid public account name")
    encoded = value.encode("utf-8")
    if len(encoded) > 255:
        raise ValueError("Public account name exceeds native u8 UTF-8 length")
    return encoded


def _modified_utf(value):
    """Java DataOutputStream.writeUTF uses modified UTF-8 of UTF-16 units."""
    result = bytearray()
    units = value.encode("utf-16-be")
    for offset in range(0, len(units), 2):
        unit = int.from_bytes(units[offset : offset + 2], "big")
        if 0 < unit < 0x80:
            result.append(unit)
        elif unit < 0x800:
            result.extend((0xC0 | (unit >> 6), 0x80 | (unit & 63)))
        else:
            result.extend(
                (0xE0 | (unit >> 12), 0x80 | ((unit >> 6) & 63), 0x80 | (unit & 63))
            )
    if len(result) > 65535:
        raise ValueError("Public account name exceeds Java modified UTF length")
    return struct.pack(">H", len(result)) + result


def auth472(account_id, dispatch_id, name):
    """cmV/cmW: success with explicit account and dispatch-account identities.

    The native consumer uses these namespaces separately. The caller supplies
    its own fixture identity policy; this serializer infers no relationship.
    eId flags (2FA, Steam, identity, email, GSM, Mac) are all false. No admin
    information is supplied, and the trailing account-property protobuf is empty.
    """
    _identity(account_id, "account identity")
    _identity(dispatch_id, "dispatch account identity")
    _name(name)
    return (
        struct.pack(">BBqqi", 0, 1, account_id, dispatch_id, 2)
        + bytes(6)
        + _modified_utf(name)
        + b"\x00"
    )


def auth457(account_id, name):
    """cmU success containing the native eDn/eDo account-information part0.

    Ordinary rights, subscriptions, benefits, times and unspecified native
    scalar fields are zero. Nickname is explicit, tag empty, community INT2.
    """
    _identity(account_id, "account identity")
    nickname = _name(name)
    part = (
        struct.pack(">qqiiBq", account_id, 0, 0, 0, 0, 0)
        + bytes(4 * 4)  # eDE: ceil(124 native rights / 32) = four words.
        + struct.pack(">B", len(nickname))
        + nickname
        + b"\x00"  # Empty tag.
        + struct.pack(">iiqqH", 2, 0, 0, 0, 0)
    )
    # fg/fh: one index entry for part0, offset6, then the part ID and body.
    inner = struct.pack(">BBiB", 1, 0, 6, 0) + part
    return b"\x00" + struct.pack(">H", len(inner)) + inner


def realms453():
    """cmY/eHZ: one public classic realm10 with a loopback game endpoint."""
    name, host = b"Wakemu", b"127.0.0.1"
    realm = (
        struct.pack(">iBB", 10, 0, len(name))
        + name
        + b"\x00"  # No translated names.
        + struct.pack(">iB", 2, 0)  # INT community, no recommendation override.
        + struct.pack(">i", len(host))
        + host
        + struct.pack(">ii", 1, 15556)
        # Multi-account, LOW population, CLASSICAL, neutral extra scalar/order.
        + struct.pack(">BiBiB", 0, 1, 0, 0, 0)
    )
    # eIf.ft delegates its second blob to eEI.dT, which starts with an i32
    # property count. An empty property map is four zero bytes, not no bytes.
    configuration = struct.pack(">iiiiB", 10, 0, 4, 0, 0)
    return struct.pack(">i", 1) + realm + struct.pack(">i", 1) + configuration + b"\x00"
