import struct
import unittest
from wakfu_server import social
from wakfu_server.company_authority import CompanySnapshot


class SocialTests(unittest.TestCase):
    def test_companion_list_is_authoritatively_empty(self):
        self.assertEqual(social.adapt(22790, b"\x02inherited companions", 9), b"\x00")
        self.assertEqual(social.adapt(22731, struct.pack(">h", 123), 9), b"\xff\xff")

    def test_market_average_prices_are_empty_compressed_records(self):
        import zlib

        self.assertEqual(
            zlib.decompress(social.adapt(14303, b"inherited prices", 9)), b""
        )

    def test_original_friend_and_ignore_payload_is_not_replayed(self):
        original = b"original-account friends and blocked users"
        self.assertEqual(social.adapt(630, original, 9), b"")
        # 752 is the moderator chat flag, not a friend-list count.
        self.assertIsNone(social.adapt(752, b"\x00", 9))

    def test_company_contains_owned_identity_and_actual_progress(self):
        original = struct.pack(">IIqqiqIiB", 1, 1, 123, 456, 30, 0, 0, 775, 1)
        character = {
            "id": 7,
            "equipment_criterion_context": {
                "company_snapshot": CompanySnapshot(9, 7, 0, 0, 603, True).record()
            },
        }
        replacement = social.adapt(13873, original, 9, character)
        self.assertEqual(
            struct.unpack(">IIqqiqIiB", replacement), (1, 1, 9, 7, 0, 0, 0, 603, 1)
        )
        with self.assertRaises(ValueError):
            social.adapt(13873, original[:-1], 9, {"id": 7})

    def test_preselection_placeholder_cannot_supply_owned_company_rank(self):
        self.assertEqual(
            struct.unpack(">qqiqIiB", social.company(9, None)), (9, 0, 0, 0, 0, 1, 0)
        )
        with self.assertRaises(ValueError):
            social.company(9, {"id": 7})
        foreign = CompanySnapshot(10, 7, 0, 0, 603, True).record()
        with self.assertRaisesRegex(ValueError, "Foreign"):
            social.company(
                9,
                {"id": 7, "equipment_criterion_context": {"company_snapshot": foreign}},
            )

    def test_unrelated_account_sections_are_preserved(self):
        self.assertIsNone(social.adapt(13873, struct.pack(">III", 1, 4, 0), 9))
        self.assertEqual(social.adapt(1029, bytes(4), 9), bytes(4))
        with self.assertRaises(ValueError):
            social.adapt(1029, struct.pack(">I", 1), 9)

    def test_account_roster_and_nested_company_are_both_local(self):
        original = struct.pack(">IIIqhI", 2, 0, 1, 456, 148, 1) + struct.pack(
            ">qqiqIiB", 123, 456, 30, 0, 0, 775, 1
        )
        owned = [
            {
                "id": 7,
                "level": 1,
                "equipment_criterion_context": {
                    "company_snapshot": CompanySnapshot(9, 7, 0, 0, 603, True).record()
                },
            },
            {"id": 8, "level": 200},
        ]
        expected = struct.pack(">IIIqhqhI", 2, 0, 2, 7, 1, 8, 200, 1) + social.company(
            9, owned[0]
        )
        self.assertEqual(social.adapt(13873, original, 9, owned[0], owned), expected)

    def test_professions_emotes_tutorial_and_politics_use_native_defaults(self):
        for kind in (10, 13, 14, 15, 17):
            payload = bytes(8) if kind == 17 else struct.pack(">I", 3) + b"old"
            result = social.adapt(13873, struct.pack(">II", 1, kind) + payload, 9)
            self.assertEqual(
                result, struct.pack(">II", 1, kind) + social.ACCOUNT_DEFAULTS[kind]
            )

    def test_public_government_removed_without_replacing_other_regions(self):
        old = struct.pack(">Bi", 17, 30) + b"Governor Togepi"
        other = b"\x02weather state"
        original = (
            struct.pack(">iI", 30, len(old))
            + old
            + struct.pack(">iI", 33, len(other))
            + other
        )
        minimal = struct.pack(">Bi", 17, 30) + bytes(49)
        expected = (
            struct.pack(">iI", 30, 54)
            + minimal
            + struct.pack(">iI", 33, len(other))
            + other
        )
        self.assertEqual(social.adapt(15984, original, 9), expected)
        self.assertIsNone(
            social.adapt(15984, struct.pack(">iI", 33, len(other)) + other, 9)
        )

    def test_account_cosmetic_bundle_clears_both_sections(self):
        original = (
            struct.pack(">III", 2, 8, 4)
            + b"skin"
            + struct.pack(">II", 9, 6)
            + b"preset"
        )
        self.assertEqual(
            social.adapt(13873, original, 9), struct.pack(">IIIII", 2, 8, 0, 9, 0)
        )
        with self.assertRaises(ValueError):
            social.adapt(13873, original[:-1], 9)

    def test_native_account_defaults_reset_optional_progress(self):
        for kind in (7, 8, 9, 11, 12, 18):
            native = social.ACCOUNT_DEFAULTS[kind]
            packet = struct.pack(">II", 1, kind) + native
            self.assertEqual(social.adapt(13873, packet, 9), packet)
        # Native unlocked categories 2 and 1 remain present for a fresh account.
        self.assertEqual(social.ACCOUNT_DEFAULTS[12].hex(), "000000080a0208020a020801")
