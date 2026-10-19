"""Immutable protobuf facts are reused without caching combat authority."""
import unittest
from unittest.mock import patch
from wakfu_server.combat.combat_effect_removal import (
    _identity_fields,
    _parse_identity_fields,
    _cached_identity_fields,
    _cached_hex_identity_fields,
    _readonly_hex_identity_fields,
)


class IdentityParserCacheTests(unittest.TestCase):
    def setUp(self):
        _cached_identity_fields.cache_clear()
        _cached_hex_identity_fields.cache_clear()

    def test_repeated_payload_reuses_parse_and_returns_private_containers(self):
        payload = b"\x08\x01\x18\x03\x2a\x02ab"
        with patch(
            "wakfu_server.combat.combat_effect_removal._parse_identity_fields",
            wraps=_parse_identity_fields,
        ) as parse:
            messages = {}
            fields = _identity_fields(payload, messages=messages)
            fields[1] = 99
            messages[5] = b"changed"
            again = {}
            self.assertEqual(_identity_fields(payload, messages=again), {1: 1, 3: 3})
            self.assertEqual(again, {5: b"ab"})
            self.assertEqual(parse.call_count, 1)
        self.assertEqual(_identity_fields(b"\x08\x02"), {1: 2})

    def test_field_selection_and_message_validation_have_distinct_keys(self):
        payload = b"\x08\x01\x18\x03"
        self.assertEqual(_identity_fields(payload, integer_fields=(3,)), {3: 3})
        self.assertEqual(_identity_fields(payload), {1: 1, 3: 3})
        duplicate = b"\x2a\x01a\x2a\x01b"
        self.assertEqual(_identity_fields(duplicate), {})
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            _identity_fields(duplicate, messages={})

    def test_malformed_and_prepopulated_messages_preserve_original_semantics(self):
        payload = b"\x2a\x01a\x08"
        for parser in (_parse_identity_fields, _identity_fields):
            messages = {}
            with self.assertRaisesRegex(ValueError, "Truncated"):
                parser(payload, messages=messages)
            self.assertEqual(messages, {5: b"a"})
            with self.assertRaisesRegex(ValueError, "Duplicate"):
                parser(b"\x2a\x01a", messages={5: b"prior"})
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            _identity_fields(b"\x08\x01\x08\x02")

    def test_full_population_with_field_variant_does_not_thrash_cache(self):
        payloads = [b"\x09" + value.to_bytes(8, "little") for value in range(512)]
        with patch(
            "wakfu_server.combat.combat_effect_removal._parse_identity_fields",
            wraps=_parse_identity_fields,
        ) as parse:
            for _ in range(10):
                for payload in payloads:
                    self.assertEqual(_identity_fields(payload), {})
                self.assertEqual(_identity_fields(payloads[0], integer_fields=(3,)), {})
            self.assertEqual(parse.call_count, 513)
        self.assertEqual(_cached_identity_fields.cache_info().hits, 4617)

    def test_cache_is_bounded_and_mutable_or_large_inputs_bypass(self):
        for value in range(4200):
            # Unknown fixed-width fields are valid and produce distinct bytes.
            _identity_fields(b"\x09" + value.to_bytes(8, "little"))
        self.assertEqual(_cached_identity_fields.cache_info().currsize, 4096)
        before = _cached_identity_fields.cache_info()
        self.assertEqual(_identity_fields(bytearray(b"\x08\x01")), {1: 1})
        self.assertEqual(_identity_fields((b"\x09" + bytes(8)) * 512), {})
        self.assertEqual(_cached_identity_fields.cache_info(), before)

    def test_hex_facts_reuse_readonly_results_without_changing_public_parser(self):
        payload = b"\x08\x01\x18\x03"
        first = _readonly_hex_identity_fields(payload.hex())
        self.assertIs(first, _readonly_hex_identity_fields(payload.hex()))
        self.assertEqual(first, {1: 1, 3: 3})
        with self.assertRaises(TypeError):
            first[1] = 99
        mutable = _identity_fields(payload)
        mutable[1] = 99
        self.assertEqual(_readonly_hex_identity_fields(payload.hex())[1], 1)
        self.assertEqual(_identity_fields(payload)[1], 1)
        self.assertEqual(_cached_hex_identity_fields.cache_info().misses, 1)

    def test_hex_cache_is_bounded_and_large_or_subclass_input_bypasses(self):
        for value in range(4200):
            _readonly_hex_identity_fields((b"\x09" + value.to_bytes(8, "little")).hex())
        self.assertEqual(_cached_hex_identity_fields.cache_info().currsize, 4096)
        before = _cached_hex_identity_fields.cache_info()
        self.assertEqual(
            _readonly_hex_identity_fields((b"\x09" + bytes(8)).hex() * 512), {}
        )

        class HexString(str):
            pass

        self.assertEqual(_readonly_hex_identity_fields(HexString("0801")), {1: 1})
        with self.assertRaises(TypeError):
            _readonly_hex_identity_fields(b"0801")
        self.assertEqual(_cached_hex_identity_fields.cache_info(), before)

    def test_hex_cache_does_not_cache_malformed_input_or_hide_changed_content(self):
        self.assertEqual(_readonly_hex_identity_fields("0801"), {1: 1})
        self.assertEqual(_readonly_hex_identity_fields("0802"), {1: 2})
        for malformed in ("08", "00", "08010802", "invalid", "0"):
            before = _cached_hex_identity_fields.cache_info().currsize
            with self.assertRaises(ValueError):
                _readonly_hex_identity_fields(malformed)
            self.assertEqual(_cached_hex_identity_fields.cache_info().currsize, before)


if __name__ == "__main__":
    unittest.main()
