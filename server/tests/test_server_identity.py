"""Protocol and validation contracts for the configurable server display name."""
import struct
import unittest

from protocol_codec import Reader
from wakfu_server.server_identity import rename_realm, validate_server_name


def _text(value, width="B"):
    encoded = value.encode("utf-8")
    return struct.pack(">" + width, len(encoded)) + encoded


def _realm(realm_id, name, localized=(), marker=0):
    body = struct.pack(">iB", realm_id, marker & 1)
    if marker & 1:
        body += struct.pack(">i", 0x12340000 + realm_id)
    body += _text(name)
    body += struct.pack(">B", len(localized))
    for locale, label in localized:
        body += struct.pack(">B", locale) + _text(label)
    body += struct.pack(">iB", 0x76540000 + realm_id, (marker >> 1) & 1)
    if marker & 2:
        body += struct.pack(">i", 0x23450000 + realm_id)
    host = f"realm-{realm_id}.example"
    body += _text(host, "I")
    ports = (10000 + realm_id, 20000 + realm_id)
    body += struct.pack(">i" + "i" * len(ports), len(ports), *ports)
    body += struct.pack(
        ">BiBiB",
        marker & 1,
        0x34560000 + realm_id,
        (marker >> 1) & 1,
        0x45670000 + realm_id,
        marker & 1,
    )
    return body


def _config(realm_id):
    first = struct.pack(">i", realm_id * 3)
    second = struct.pack(">i", realm_id * 5)
    return (
        struct.pack(">ii", realm_id, len(first))
        + first
        + struct.pack(">i", len(second))
        + second
        + b"\x01"
    )


def _packet(realm_count=300, include_local=True):
    realms = []
    for realm_id in range(realm_count):
        if realm_id == 10:
            realms.append(
                _realm(
                    realm_id,
                    "Old Rubilax",
                    ((0, "Old EN"), (1, "Old FR"), (2, "Old ES")),
                    3,
                )
            )
        else:
            realms.append(
                _realm(
                    realm_id,
                    f"Realm {realm_id}",
                    ((0, f"EN {realm_id}"),),
                    realm_id % 4,
                )
            )
    if not include_local:
        realms = [_realm(i, f"Realm {i}") for i in range(realm_count) if i != 10]
    configs = [_config(i) for i in range(realm_count)]
    return (
        struct.pack(">i", len(realms))
        + b"".join(realms)
        + struct.pack(">i", len(configs))
        + b"".join(configs)
        + b"\xA5"
    )


def _read_packet(body):
    reader = Reader(body)
    realms = []
    for _ in range(reader.number("i")):
        start = reader.pos
        realm_id = reader.number("i")
        if reader.number("B"):
            reader.take(4)
        name = reader.text("B")
        localized = [
            (reader.number("B"), reader.text("B")) for _ in range(reader.number("B"))
        ]
        reader.take(4)
        if reader.number("B"):
            reader.take(4)
        reader.text("I")
        reader.take(4 * reader.number("i"))
        reader.take(1 + 4 + 1 + 4 + 1)
        realms.append((realm_id, name, localized, body[start : reader.pos]))
    configs = []
    for _ in range(reader.number("i")):
        start = reader.pos
        realm_id = reader.number("i")
        reader.take(reader.number("i"))
        reader.take(reader.number("i"))
        reader.take(1)
        configs.append((realm_id, body[start : reader.pos]))
    flags = reader.take(1)
    reader.finish()
    return realms, configs, flags


class ServerIdentityProtocolTests(unittest.TestCase):
    def test_rename_changes_local_realm_names_only_and_preserves_large_packet(self):
        source = _packet()
        name = "Rubilax — Étoile 東京"
        result = rename_realm(source, name)
        realms, configs, flags = _read_packet(result)
        original_realms, original_configs, original_flags = _read_packet(source)

        self.assertEqual(len(realms), 300)
        self.assertEqual(len(configs), 300)
        self.assertEqual(flags, original_flags)
        self.assertEqual(configs, original_configs)
        self.assertEqual(realms[10][1], name)
        self.assertEqual([label for _, label in realms[10][2]], [name, name, name])
        for index, realm in enumerate(realms):
            if index != 10:
                self.assertEqual(realm, original_realms[index])

    def test_name_validation_enforces_character_byte_and_whitespace_rules(self):
        for value in (
            "",
            "  Rubilax",
            "Rubilax ",
            "x" * 81,
            "😀" * 64,
            "A\x00B",
            "x\u200b",
        ):
            with self.subTest(value=repr(value)):
                with self.assertRaises(ValueError):
                    validate_server_name(value)
        self.assertEqual(validate_server_name("😀" * 63), "😀" * 63)

    def test_malformed_or_missing_local_realm_is_rejected_without_partial_output(self):
        valid = _packet()
        malformed_packets = (
            valid[:-1],
            valid + b"\x00",
            _packet(include_local=False),
            struct.pack(">iiB", -1, 0, 0),
            struct.pack(">iiB", 0, -1, 0),
        )
        for malformed in malformed_packets:
            with self.subTest(length=len(malformed)):
                with self.assertRaises(ValueError):
                    rename_realm(malformed, "Rubilax")


if __name__ == "__main__":
    unittest.main()
