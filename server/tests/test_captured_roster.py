"""Offline native captured-roster codec and ownership contracts."""
import unittest
from wakfu_server.characters.captured_roster import (
    CapturedCreature,
    NativeCapturedRoster,
    OwnedCapturedRoster,
    selected_availability_status,
    captured_profile_seeds,
)


class CapturedRosterTests(unittest.TestCase):
    def test_native_field_order_signed_values_and_utf8(self):
        roster = NativeCapturedRoster((CapturedCreature(9, -32768, "é", -2),), -1)
        expected = bytes.fromhex("01098000fffe0002c3a9ff")
        self.assertEqual(roster.encode(), expected)
        self.assertEqual(NativeCapturedRoster.decode(expected), roster)

    def test_empty_and_non_slot_selection_are_preserved(self):
        for selection in (-128, -1, 0, 9, 127):
            source = NativeCapturedRoster((), selection)
            own = OwnedCapturedRoster.import_native(42, source, lambda profile: None)
            self.assertEqual(own.selected_slot, selection)
            self.assertIsNone(own.selected_creature)
            self.assertEqual(own.free_slots, 10)
            self.assertEqual(own.to_native().encode(), source.encode())

    def test_resolver_filters_only_actual_roster_seeds(self):
        calls = []

        def resolve(profile):
            calls.append(profile)
            return object() if profile == 7 else None

        source = NativeCapturedRoster(
            (CapturedCreature(2, 7, "owned"), CapturedCreature(3, 8, "unresolved")), 2
        )
        own = OwnedCapturedRoster.import_native(42, source, resolve)
        self.assertEqual(calls, [7, 8])
        self.assertEqual(own.selected_creature.profile_id, 7)
        self.assertEqual(own.free_slots, 9)
        self.assertEqual(own.available, (False, False, True) + (False,) * 7)

    def test_invalid_slots_ignored_duplicate_valid_slot_last_write_wins(self):
        source = NativeCapturedRoster(
            (
                CapturedCreature(-1, 1, "bad"),
                CapturedCreature(10, 2, "bad"),
                CapturedCreature(1, 3, "first"),
                CapturedCreature(1, 4, "last"),
            ),
            1,
        )
        own = OwnedCapturedRoster.import_native(42, source, lambda profile: object())
        self.assertEqual(own.free_slots, 9)
        self.assertEqual(own.selected_creature.name, "last")

    def test_owned_export_does_not_filter_unavailable_occupied_slots(self):
        entry = CapturedCreature(0, 7, "owned")
        own = OwnedCapturedRoster(42, (entry,) + (None,) * 9)
        self.assertEqual(own.to_native().entries, (entry,))

    def test_persisted_record_roundtrip_and_owner_guard(self):
        own = OwnedCapturedRoster.import_native(
            42,
            NativeCapturedRoster((CapturedCreature(9, 7, "own"),), 9),
            lambda profile: object(),
        )
        record = own.to_record()
        self.assertEqual(
            OwnedCapturedRoster.from_record(record, expected_owner_id=42), own
        )
        with self.assertRaises(ValueError):
            OwnedCapturedRoster.from_record(record, expected_owner_id=43)

    def test_malformed_record_arrays_and_slot_identity(self):
        record = OwnedCapturedRoster(42).to_record()
        for key, value in (
            ("slots", []),
            ("available", [0] * 10),
            ("slots", [{"slot": 2, "profile_id": 3, "name": "bad"}] + [None] * 9),
        ):
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                OwnedCapturedRoster.from_record(
                    {**record, key: value}, expected_owner_id=42
                )

    def test_all_truncations_and_trailing_bytes_are_rejected(self):
        wire = NativeCapturedRoster((CapturedCreature(1, 2, "abc"),), 1).encode()
        for end in range(len(wire)):
            with self.subTest(end=end), self.assertRaises(ValueError):
                NativeCapturedRoster.decode(wire[:end])
        with self.assertRaises(ValueError):
            NativeCapturedRoster.decode(wire + b"x")

    def test_native_utf8_decoder_replaces_invalid_sequences(self):
        source = bytes.fromhex("0101000200010001ff00")
        self.assertEqual(NativeCapturedRoster.decode(source).entries[0].name, "\ufffd")

    def test_selected_native_status_and_actual_profile_seeds(self):
        entry = CapturedCreature(0, 7, "own")
        slots = (entry,) + (None,) * 9
        self.assertEqual(selected_availability_status(OwnedCapturedRoster(42)), -1)
        self.assertEqual(
            selected_availability_status(OwnedCapturedRoster(42, slots)), -2
        )
        own = OwnedCapturedRoster(42, slots, (True,) + (False,) * 9)
        self.assertEqual(selected_availability_status(own), 0)
        self.assertEqual(captured_profile_seeds(own), (7,))
        with self.assertRaises(ValueError):
            selected_availability_status(None)

    def test_wire_domain_limits_and_boolean_integer_rejection(self):
        for args in ((128, 1, ""), (1, 32768, ""), (True, 1, ""), (1, 1, "x" * 65536)):
            with self.subTest(args=args[:2]), self.assertRaises(ValueError):
                CapturedCreature(*args)
        with self.assertRaises(ValueError):
            NativeCapturedRoster((), 128)
        with self.assertRaises(ValueError):
            NativeCapturedRoster((CapturedCreature(0, 1, ""),) * 256)


if __name__ == "__main__":
    unittest.main()
