"""Strict adapters for native social requests and response packets.

The client request name is its character-name field. The authority resolves it
through ``characters.name_key`` and stores the resulting account ID; it never
guesses an account's principal character.
"""
import struct

from wakfu_server.social_wire import encode_friend_lists


def _body_bytes(body):
    if not isinstance(body, (bytes, bytearray, memoryview)):
        raise ValueError("Social request body must be bytes")
    return bytes(body)


def _name(data, offset=0):
    if offset >= len(data):
        raise ValueError("Truncated social character-name length")
    length = data[offset]
    offset += 1
    if length == 0 or offset + length > len(data):
        raise ValueError("Invalid social character-name length")
    try:
        value = data[offset : offset + length].decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError("Invalid social character-name UTF-8") from error
    return value, offset + length


def decode_request(opcode, body):
    data = _body_bytes(body)
    if opcode in (784, 657):
        name, offset = _name(data)
        if offset != len(data):
            raise ValueError("Trailing social request bytes")
        return {"character_name": name}
    if opcode in (672, 799):
        if len(data) != 8:
            raise ValueError("Contact removal requires exactly one i64 account ID")
        account_id = struct.unpack(">q", data)[0]
        if account_id <= 0:
            raise ValueError("Invalid contact account ID")
        return {"account_id": account_id}
    if opcode == 12449:
        if data:
            raise ValueError("Native DND request has an empty body")
        return {}
    raise ValueError("Unsupported native social request")


def _account_id(contact):
    value = contact.get("account_id") if isinstance(contact, dict) else None
    if type(value) is not int or not 0 < value < (1 << 63):
        raise ValueError("Invalid social ACK account ID")
    return value


def _native_name(contact, field):
    value = contact.get(field) if isinstance(contact, dict) else None
    if not isinstance(value, str) or not value:
        raise ValueError(f"Social ACK requires {field}")
    encoded = value.encode("utf-8")
    if len(encoded) > 255:
        raise ValueError(f"Social ACK {field} exceeds native byte length")
    return bytes((len(encoded),)) + encoded


def encode_add_friend_ack(contact):
    """Encode NS/718 using the exact requested character's stored profile."""
    account_id = _account_id(contact)
    account_name = _native_name(contact, "account_name")
    character_name = _native_name(contact, "character_name")
    breed_id = contact.get("breed_id")
    sex = contact.get("sex")
    xp = contact.get("xp")
    if type(breed_id) is not int or not -(1 << 15) <= breed_id < (1 << 15):
        raise ValueError("Invalid native social breed ID")
    if type(sex) is not int or sex not in (0, 1):
        raise ValueError("Invalid native social sex")
    if type(xp) is not int or not 0 <= xp < (1 << 63):
        raise ValueError("Invalid native social character XP")
    return (
        account_name
        + character_name
        + struct.pack(">qhBq", account_id, breed_id, sex, xp)
    )


def encode_add_ignore_ack(contact):
    """Encode NX/641; the character profile comes from the request name."""
    return (
        struct.pack(">q", _account_id(contact))
        + _native_name(contact, "account_name")
        + _native_name(contact, "character_name")
    )


def encode_remove_friend_ack(account_id):
    return struct.pack(">q", _account_id({"account_id": account_id}))


def encode_remove_ignore_ack(contact):
    return struct.pack(">q", _account_id(contact)) + _native_name(
        contact, "account_name"
    )


def encode_dnd_status(enabled):
    if type(enabled) is not bool:
        raise ValueError("DND status must be bool")
    return bytes((int(enabled),))


def encode_bootstrap(snapshot):
    if not isinstance(snapshot, dict) or set(snapshot) - {
        "friends",
        "ignored",
        "do_not_disturb",
    }:
        raise ValueError("Invalid social bootstrap snapshot")
    friends = snapshot.get("friends")
    ignored = snapshot.get("ignored")
    if not isinstance(friends, (list, tuple)) or not isinstance(ignored, (list, tuple)):
        raise ValueError("Social bootstrap lists must be sequences")
    return encode_friend_lists(friends, ignored)


class SocialDispatcher:
    """Service adapter root can call from the authenticated opcode loop."""

    def __init__(self, contacts):
        self.contacts = contacts

    def bootstrap(self, account_id, generation):
        snapshot = self.contacts.snapshot(account_id, generation)
        return [
            (630, encode_bootstrap(snapshot)),
            (711, encode_dnd_status(snapshot["do_not_disturb"])),
        ]

    def handle(self, opcode, body, account_id, generation):
        request = decode_request(opcode, body)
        if opcode == 784:
            contact = self.contacts.add_friend(
                account_id, generation, request["character_name"]
            )
            return (718, encode_add_friend_ack(contact))
        if opcode == 657:
            contact = self.contacts.add_ignore(
                account_id, generation, request["character_name"]
            )
            return (641, encode_add_ignore_ack(contact))
        if opcode == 672:
            contact_id = request["account_id"]
            if not self.contacts.remove_friend(account_id, generation, contact_id):
                return None
            return (719, encode_remove_friend_ack(contact_id))
        if opcode == 799:
            contact = self.contacts.remove_ignore_contact(
                account_id, generation, request["account_id"]
            )
            if contact is None:
                return None
            return (765, encode_remove_ignore_ack(contact))
        if opcode == 12449:
            enabled = self.contacts.toggle_do_not_disturb(account_id, generation)
            return (711, encode_dnd_status(enabled))
        raise ValueError("Unsupported native social request")
