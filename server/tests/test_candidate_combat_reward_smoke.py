import struct
import unittest

from tools.candidate_combat_reward_smoke import (
    _candidate_database,
    decode_fight_report,
    decode_wallet_section,
    decode_wallet_update,
    decode_xp_notification,
    _decode_temporary_section,
)


def _v(value):
    result = bytearray()
    while value > 0x7F:
        result.append((value & 0x7F) | 0x80)
        value >>= 7
    result.append(value)
    return bytes(result)


def _field(number, wire, value):
    tag = _v((number << 3) | wire)
    if wire == 0:
        return tag + _v(value)
    if wire == 2:
        return tag + _v(len(value)) + value
    raise AssertionError("Test fixture uses only varint and length fields")


class CandidateCombatRewardSmokeTests(unittest.TestCase):
    def test_candidate_database_guard_rejects_non_candidate_database(self):
        _candidate_database("dbname=wakemu_candidate_smoke_example")
        for url in (
            "dbname=wakemu_migration_test",
            "dbname=wakemu",
            "host=postgres user=wakemu",
        ):
            with self.subTest(database=url), self.assertRaisesRegex(
                ValueError, "disposable candidate"
            ):
                _candidate_database(url)

    def test_native_13613_decoder_checks_identity_delta_and_crosslevel(self):
        character_id = 501
        payload = struct.pack(">BBqqhB", 1, 1, character_id, 999, 1, 0)
        self.assertEqual(decode_xp_notification(character_id, payload), (999, 1))
        with self.assertRaisesRegex(AssertionError, "identity/layout"):
            decode_xp_notification(character_id + 1, payload)
        with self.assertRaisesRegex(AssertionError, "length"):
            decode_xp_notification(character_id, payload[:-1])

    def test_native_wallet_decoders_accept_only_absolute_nonnegative_totals(self):
        self.assertEqual(decode_wallet_update(struct.pack(">q", 9876)), 9876)
        self.assertEqual(decode_wallet_section(struct.pack(">IIq", 1, 6, 9876)), 9876)
        for payload, decoder in (
            (struct.pack(">q", -1), decode_wallet_update),
            (b"\x00" * 7, decode_wallet_update),
            (struct.pack(">IIq", 1, 5, 9876), decode_wallet_section),
            (struct.pack(">IIq", 1, 6, -1), decode_wallet_section),
        ):
            with self.subTest(payload=payload), self.assertRaises(AssertionError):
                decoder(payload)

    def test_temporary_bootstrap_section_checks_length_and_native_repeated_items(self):
        item_a = _field(1, 0, 1001) + _field(2, 0, 2)
        item_b = _field(1, 0, 1002) + _field(2, 0, 1)
        payload = _field(1, 2, item_a) + _field(1, 2, item_b)
        section = struct.pack(">h", len(payload)) + payload
        self.assertEqual(_decode_temporary_section(section), [item_a, item_b])
        with self.assertRaisesRegex(AssertionError, "length"):
            _decode_temporary_section(struct.pack(">h", len(payload) - 1) + payload)
        self.assertEqual(_decode_temporary_section(b"\x00\x00"), [])

    def test_native_12755_decoder_reads_player_progression_and_kamas(self):
        xp = _field(1, 0, 5000) + _field(2, 0, 999) + _field(5, 0, 1) + _field(6, 0, 2)
        player = (
            _field(1, 0, 501)
            + _field(2, 0, 42)
            + _field(3, 2, b"Smoke")
            + _field(4, 0, 8)
            + _field(5, 0, 1)
            + _field(6, 0, 0)
            + _field(
                7,
                2,
                _field(1, 0, 2024)
                + _field(2, 0, 2)
                + _field(3, 0, 0)
                + _field(4, 0, 0),
            )
            + _field(8, 2, xp)
            + _field(9, 0, 37)
            + _field(10, 0, 0)
        )
        winning_team = _field(1, 0, 0) + _field(2, 2, player)
        losing_team = _field(1, 0, 1)
        report = (
            _field(1, 0, 7)
            + _field(2, 0, 1)
            + _field(3, 0, 1)
            + _field(4, 0, 0)
            + _field(5, 2, winning_team)
            + _field(6, 2, losing_team)
            + _field(7, 0, 501)
            + _field(8, 0, 2)
            + _field(14, 0, 1)
        )
        frame_body = struct.pack(">iii", 7, 1, -1) + report
        self.assertEqual(
            decode_fight_report(7, frame_body),
            dict(
                character_id=501,
                end_xp=5000,
                won_xp=999,
                start_level=1,
                end_level=2,
                kamas=37,
                loots=[
                    dict(
                        reference=2024,
                        quantity=2,
                        is_purse_loot=False,
                        is_pvp_loot=False,
                    )
                ],
            ),
        )
        with self.assertRaisesRegex(AssertionError, "different fight"):
            decode_fight_report(8, frame_body)


if __name__ == "__main__":
    unittest.main()
