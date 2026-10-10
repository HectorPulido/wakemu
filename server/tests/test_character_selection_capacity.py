"""Native signed-byte capacity agrees across configuration and wire encoding."""
import os
import struct
import unittest
from unittest.mock import patch
from wakfu_server.characters.selection_capacity import (
    configured_capacity,
    packet,
    NATIVE_MAX_CHARACTERS,
)
from wakfu_server.storage.store import Store
from wakfu_server import wire


class CharacterSelectionCapacityTests(unittest.TestCase):
    def test_eighteen_is_default_for_store_and_ui(self):
        with patch.dict(os.environ, {}, clear=True), patch(
            "wakfu_server.storage.store.Database"
        ):
            store = Store("dbname=offline-test")
            self.assertEqual(store.max_characters, 18)
            self.assertEqual(packet(store.max_characters), (23992, b"\x0d"))

    def test_explicit_and_environment_overrides_have_same_ui_limit(self):
        for limit in (1, 5, 18, 24, 127):
            with self.subTest(limit=limit), patch.dict(
                os.environ, {"WAKFU_MAX_CHARACTERS": str(limit)}
            ), patch("wakfu_server.storage.store.Database"):
                store = Store("dbname=offline-test")
                explicit = Store("dbname=offline-test", max_characters=limit)
                self.assertEqual(store.max_characters, explicit.max_characters)
                self.assertEqual(struct.unpack(">b", packet(limit)[1])[0] + 5, limit)
        with patch.dict(os.environ, {"WAKFU_MAX_CHARACTERS": "24"}):
            self.assertEqual(configured_capacity(5), 5)

    def test_invalid_capacities_cannot_overflow_or_wrap_native_fields(self):
        for limit in (0, 128, -1, True, 5.0, "24"):
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                configured_capacity(limit)
        with patch.dict(os.environ, {"WAKFU_MAX_CHARACTERS": "nonsense"}):
            with self.assertRaises(ValueError):
                configured_capacity()

    def test_roster_signed_count_boundary_and_no_companion_records(self):
        template = b"\x01" + struct.pack(">I", 1) + b"x"
        characters = [{}] * NATIVE_MAX_CHARACTERS
        with patch.object(wire, "minimal_entity", return_value=b"x"), patch.object(
            wire, "header", return_value=b"x"
        ):
            encoded = wire.character_list(template, 42, characters)
            self.assertEqual(struct.unpack_from(">b", encoded)[0], 127)
            self.assertEqual(encoded[-1:], b"\x00")
            with self.assertRaisesRegex(ValueError, "signed-byte"):
                wire.character_list(template, 42, characters + [{}])
