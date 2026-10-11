"""Balance boundaries and native exact-rounding regression checks."""
import csv
import os
from pathlib import Path
import unittest
import struct
from contextlib import nullcontext
from unittest.mock import Mock, patch
from wakfu_server.planting_level_policy import bonus, validate
from wakfu_server.planting_probability import calculate
from wakfu_server.planting_bonus_wire import delta_packet, publication, snapshot_section


class PlantingLevelPolicyTests(unittest.TestCase):
    def test_level_bonus_progresses_every_two_levels_and_caps_at_one_hundred(self):
        previous = 0
        for level in range(1001):
            actual = bonus(level)
            self.assertEqual(min(level // 2, 100), actual)
            self.assertGreaterEqual(actual, previous)
            previous = actual
        self.assertEqual(125, bonus(200, authoritative_bonus=25))
        self.assertEqual(-25, bonus(0, authoritative_bonus=-25))

    def test_configured_rate_and_cap_are_authoritative(self):
        policy = dict(version=1, levels_per_point=4, maximum_level_bonus=30)
        self.assertEqual(25, bonus(100, policy=policy))
        self.assertEqual(30, bonus(200, policy=policy))
        for bad in (
            None,
            {},
            dict(policy, enabled=True),
            dict(policy, levels_per_point=0),
            dict(policy, maximum_level_bonus=101),
            dict(policy, version=True),
        ):
            with self.subTest(policy=bad), self.assertRaises(ValueError):
                validate(bad)
        for level in (True, -1, 32768, 1.5):
            with self.subTest(level=level), self.assertRaises(ValueError):
                bonus(level)
        with self.assertRaises(ValueError):
            bonus(200, authoritative_bonus=(1 << 31) - 1)

    def test_every_soil_and_level_remains_bounded_and_monotone(self):
        for terrain in range(101):
            for compatible in (True, False):
                previous = 0.0
                for level in range(201):
                    value = calculate(
                        ground_percent=terrain,
                        climate_compatible=compatible,
                        profession_bonus_percent=bonus(level),
                    )
                    self.assertGreaterEqual(value["probability"], previous)
                    self.assertLessEqual(value["probability"], 1.0)
                    self.assertEqual(value["displayed_percent"] == -1, terrain == 0)
                    previous = value["probability"]

    def test_native_float_intermediate_preserves_rounding_boundary(self):
        value = calculate(
            ground_percent=50, climate_compatible=True, profession_bonus_percent=1
        )
        self.assertEqual(0.5049999998882413, value["probability"])
        self.assertEqual(50, value["displayed_percent"])

    def test_snapshot_encodes_valid_owned_bonuses_and_rejects_invalid_input(self):
        value = snapshot_section(42, {71: 25, 72: 50}, first_uid=100)
        self.assertEqual(1, value[0])
        self.assertEqual(0, value[-1])
        for args in (
            (True, {}, 100),
            (42, {True: 1}, 100),
            (42, {71: False}, 100),
            (42, {71: 1, 72: 2}, (1 << 63) - 1),
        ):
            with self.subTest(args=args), self.assertRaises(ValueError):
                snapshot_section(args[0], args[1], first_uid=args[2])

    def test_publication_sends_only_owned_profession_deltas_without_mutating_baseline(
        self,
    ):
        store = Mock()
        store.connection.return_value = nullcontext(Mock())
        previous = {71: 50, 72: 25, 74: 3}
        uid = iter((100, 101, 102))
        action = iter((200, 201, 202))
        with patch(
            "wakfu_server.planting_level_policy.account_bonuses",
            return_value={71: 25, 72: 25, 73: 10},
        ):
            result = publication(
                store,
                {"id": 42, "account_id": 7},
                previous,
                allocate_uid=lambda: next(uid),
                allocate_action=lambda: next(action),
            )
        self.assertEqual({71: 50, 72: 25, 74: 3}, previous)
        self.assertEqual({71: 25, 72: 25, 73: 10}, result["bonuses"])
        self.assertEqual(4, len(result["packets"]))
        self.assertEqual((13420, struct.pack(">i", -1)), result["packets"][-1])
        for packet, profession, delta, assigned_uid, assigned_action in zip(
            result["packets"],
            (71, 73, 74),
            (-25, 10, -3),
            (100, 101, 102),
            (200, 201, 202),
        ):
            self.assertEqual(
                delta_packet(
                    42, profession, delta, uid=assigned_uid, action_id=assigned_action
                ),
                packet,
            )
            self.assertEqual(
                (-1, assigned_action, -1, 0, 2000),
                struct.unpack(">iiiBi", packet[1][:17]),
            )

    def test_matching_publication_has_no_packets_or_new_uids(self):
        store = Mock()
        store.connection.return_value = nullcontext(Mock())
        allocate = Mock(side_effect=AssertionError("unchanged bonus must not allocate"))
        with patch(
            "wakfu_server.planting_level_policy.account_bonuses", return_value={71: 25}
        ):
            result = publication(
                store,
                {"id": 42, "account_id": 7},
                {71: 25},
                allocate_uid=allocate,
                allocate_action=allocate,
            )
        self.assertEqual([], result["packets"])

    @unittest.skipUnless(
        os.environ.get("WAKFU_PLANTING_NATIVE_ORACLE"), "Native Java oracle required"
    )
    def test_native_java_matrix_matches_probability_and_display_exactly(self):
        path = Path(os.environ["WAKFU_PLANTING_NATIVE_ORACLE"])
        count = 0
        with path.open() as source:
            for row in csv.DictReader(source):
                actual = calculate(
                    ground_percent=int(row["terrain"]),
                    climate_compatible=row["compatible"] == "true",
                    profession_bonus_percent=int(row["bonus"]),
                )
                self.assertEqual(float(row["probability"]), actual["probability"], row)
                self.assertEqual(
                    int(row["displayed"]), actual["displayed_percent"], row
                )
                count += 1
        self.assertEqual(60802, count)
