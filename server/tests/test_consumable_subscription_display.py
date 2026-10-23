"""Retained native subscription wrappers show their actual state counter."""
import copy
import json
from pathlib import Path
import struct
import unittest

from wakfu_server.consumable_buff_wire import snapshot, delta
from wakfu_server.wire import proto_fields


class ConsumableSubscriptionDisplayTests(unittest.TestCase):
    @staticmethod
    def character(reference, *, level=None, map_id=546):
        rows = json.loads(
            (
                Path(__file__).parents[1] / "protocol/native-consumable-actions.json"
            ).read_text()
        )["items"]
        state = copy.deepcopy(
            next(row for row in rows if row["item_ref"] == reference)["plan"]["states"][
                0
            ]
        )
        state.update(uid=9001, remaining_ms=state["duration_ms"])
        if level is not None:
            state["level"] = level
        return dict(
            id=40,
            map_id=map_id,
            level=200,
            hp=80,
            max_hp=100,
            consumable_states=[state],
        )

    @staticmethod
    def applications(packets):
        result = []
        for opcode, packet in packets:
            if opcode != 12613:
                continue
            fight, action, parent, execute, generic, size = struct.unpack_from(
                ">iiiBih", packet
            )
            result.append(
                (generic, execute, dict(proto_fields(packet[19 : 19 + size])))
            )
        return result

    def test_all_six_items_publish_only_the_original_subscription_root(self):
        for ref in (13858, 13862, 13886, 14055, 19095, 18422):
            with self.subTest(reference=ref):
                character = self.character(ref)
                before = copy.deepcopy(character)
                apps = self.applications(snapshot(character))
                self.assertEqual(
                    [generic for generic, execute, fields in apps], [310, 330]
                )
                root = 114509 if ref == 18422 else 282786
                generic, execute, fields = apps[1]
                self.assertEqual(execute, 0)
                self.assertEqual(fields[3 << 3], root)
                self.assertEqual(fields[4 << 3], 0)
                self.assertEqual(
                    fields[10 << 3],
                    (character["consumable_states"][0]["state_id"] << 16)
                    | character["consumable_states"][0]["level"],
                )
                self.assertEqual(character, before)

    def test_remaining_fights_are_the_actual_pl_level_and_replace_atomically(self):
        previous = None
        for level in (5, 4, 1):
            character = self.character(18422, level=level)
            apps = self.applications(snapshot(character))
            self.assertEqual(len(apps), 2)
            self.assertEqual(apps[1][2][10 << 3], (2786 << 16) | level)
            if previous is not None:
                packets = delta(previous, character)
                self.assertEqual(
                    [op for op, _ in packets], [13560, 13560, 12613, 12613, 13420]
                )
            previous = character
        self.assertEqual(
            [op for op, _ in delta(previous, dict(id=40, consumable_states=[]))],
            [13560, 13560, 13420],
        )

    def test_native_criteria_and_unknown_reactive_families_remain_separate(self):
        flags = json.loads(
            (
                Path(__file__).parents[1]
                / "wakfu_server/maps/native_world_battlegrounds.json"
            ).read_text()
        )
        battleground = next(int(key) for key, value in flags["worlds"].items() if value)
        self.assertEqual(
            [
                g
                for g, _, _ in self.applications(
                    snapshot(self.character(18422, map_id=battleground))
                )
            ],
            [310],
        )
        for ref in (18050, 18351, 18355, 18401, 18406, 19097):
            with self.subTest(reference=ref):
                self.assertNotIn(
                    330,
                    [g for g, _, _ in self.applications(snapshot(self.character(ref)))],
                )
