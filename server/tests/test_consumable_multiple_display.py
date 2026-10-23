"""Native multi-row food icons keep their carrier and child lifecycles aligned."""
import struct
import copy
import json
from pathlib import Path
import unittest

from wakfu_server.consumable_buff_wire import delta, snapshot
from wakfu_server.wire import proto_fields


class ConsumableMultipleDisplayTests(unittest.TestCase):
    # Exact native display rows: the original effect ids/order, generic ids,
    # runner families, and characteristic ids come from the pinned export.
    GROUPS = {
        1295: (
            12,
            (
                (66106, 166, "eWQ", 36),
                (66109, 162, "eWQ", 33),
                (66110, 2008, "eXx", None),
                (66111, 2006, "eXx", None),
            ),
        ),
        3332: (
            5,
            (
                (146149, 150, "eWQ", 9),
                (146150, 875, "eWQ", 87),
            ),
        ),
        4564: (
            1,
            (
                (187269, 2002, "eXx", None),
                (187270, 2003, "eXx", None),
                (187271, 2004, "eXx", None),
            ),
        ),
    }
    ACTUAL_MULTI_DISPLAY = {
        13551: (1295, (66106, 66109, 66110, 66111)),
        14484: (3332, (146149, 146150)),
        15856: (1821, (90053, 90056)),
        17728: (2330, (104729, 104730, 104731)),
        18574: (2997, (117770, 117769)),
        18576: (3026, (118584, 118585)),
        19154: (3030, (118600, 118601)),
        19155: (3029, (118596, 118597)),
        19159: (3027, (118588, 118589)),
        19161: (3028, (118592, 118593)),
        19914: (4035, (171809, 171813)),
        19915: (4036, (171814, 171815)),
        20034: (4073, (173761, 173762)),
        20170: (4147, (176105, 176106)),
        20483: (4312, (180993, 180994)),
        20824: (4564, (187269, 187270, 187271)),
    }

    @classmethod
    def state(cls, state_id, uid, remaining=892_000):
        level, definitions = cls.GROUPS[state_id]
        native_effects = {}
        for effect_id, generic, runner, stat_id in definitions:
            native_effects[str(effect_id)] = {
                "id": effect_id,
                "generic": generic,
                "runner": runner,
                "values": [100],
                "stat_id": stat_id,
                "criteria": "not IsBattleground()" if state_id == 4564 else "",
                "children": [],
                "subscription": False,
                "native_metadata": {
                    "target_masks": [None] * 7,
                    "native_target_selector": {"class": "fcE", "mask": 2},
                },
            }
        return {
            "uid": uid,
            "state_id": state_id,
            "level": level,
            "clock": "online",
            "duration_ms": 1_200_000,
            "remaining_ms": remaining,
            "effect_ids": [row[0] for row in definitions],
            "metadata": {"native_effects": native_effects},
        }

    @staticmethod
    def character(*states):
        return {"id": 42, "map_id": 1134, "consumable_states": list(states)}

    @staticmethod
    def frame(opcode, packet):
        if opcode == 13420:
            return None
        if opcode == 13560:
            fight, action, _sequence, effect_class, size = struct.unpack_from(
                ">iiiih", packet
            )
            return fight, action, effect_class, packet[18 : 18 + size]
        fight, action, _parent, execute, effect_class, size = struct.unpack_from(
            ">iiiBih", packet
        )
        return fight, action, execute, effect_class, packet[19 : 19 + size]

    @classmethod
    def native_effects(cls, packets, opcode):
        known_ids = {row[0] for _, rows in cls.GROUPS.values() for row in rows} | {
            effect_id
            for _, ids in cls.ACTUAL_MULTI_DISPLAY.values()
            for effect_id in ids
        }
        result = []
        for actual_opcode, packet in packets:
            if actual_opcode != opcode:
                continue
            frame = cls.frame(actual_opcode, packet)
            fields = dict(proto_fields(frame[-1]))
            if fields.get(3 << 3) in known_ids:
                result.append((fields[3 << 3], fields[1 << 3], frame[2]))
        return result

    @staticmethod
    def actual_state(item_ref, uid):
        catalog = json.loads(
            (
                Path(__file__).parents[1] / "protocol/native-consumable-actions.json"
            ).read_text()
        )
        row = next(item for item in catalog["items"] if item["item_ref"] == item_ref)
        state = copy.deepcopy(row["plan"]["states"][0])
        state["uid"] = uid
        state["remaining_ms"] = (
            0 if state["clock"] == "event" else state["duration_ms"] - 1_000
        )
        return state

    def test_all_sixteen_actual_catalog_groups_publish_exact_qualified_rows(self):
        catalog = json.loads(
            (
                Path(__file__).parents[1] / "protocol/native-consumable-actions.json"
            ).read_text()
        )
        items = {row["item_ref"]: row for row in catalog["items"]}
        for item_ref, (state_id, expected_ids) in self.ACTUAL_MULTI_DISPLAY.items():
            with self.subTest(item_ref=item_ref, state_id=state_id):
                plan = items[item_ref]["plan"]["states"][0]
                self.assertEqual(plan["state_id"], state_id)
                self.assertTrue(set(expected_ids).issubset(plan["effect_ids"]))
                state = self.actual_state(item_ref, 50_000 + item_ref)
                packets = snapshot(
                    self.character(state), allocate_action=iter(range(1, 80)).__next__
                )
                display = self.native_effects(packets, 12613)
                self.assertEqual([entry[0] for entry in display], list(expected_ids))
                self.assertEqual(
                    len({entry[1] for entry in display}), len(expected_ids)
                )
                self.assertTrue(all(entry[2] == 0 for entry in display))
                self.assertEqual(packets[-1], (13420, struct.pack(">i", -1)))

    def test_actual_not_battleground_group_uses_its_native_alternate_marker(self):
        normal = self.character(self.actual_state(20824, 70_824))
        battleground = {**normal, "map_id": 1161}
        normal_packets = snapshot(normal, allocate_action=iter(range(1, 30)).__next__)
        bg_packets = snapshot(
            battleground, allocate_action=iter(range(40, 70)).__next__
        )
        self.assertEqual(
            [entry[0] for entry in self.native_effects(normal_packets, 12613)],
            [187269, 187270, 187271],
        )
        # The original 252676 eXE row is the explicit BG fallback; it is not
        # one of the three active-state eXx rows and retains its own legacy UID.
        self.assertEqual(
            [
                dict(proto_fields(self.frame(opcode, packet)[-1])).get(3 << 3)
                for opcode, packet in bg_packets
                if opcode == 12613 and self.frame(opcode, packet)[3] != 310
            ],
            [252676],
        )

    def test_snapshot_sends_each_attested_row_once_with_disjoint_stable_uids(self):
        for state_id, (level, definitions) in self.GROUPS.items():
            with self.subTest(state_id=state_id):
                uid = 8_100 + state_id
                packets = snapshot(
                    self.character(self.state(state_id, uid)),
                    allocate_action=iter(range(1, 40)).__next__,
                )
                display = self.native_effects(packets, 12613)
                expected_ids = [row[0] for row in definitions]
                self.assertEqual([row[0] for row in display], expected_ids)
                self.assertEqual(len({row[1] for row in display}), len(expected_ids))
                legacy_uid = uid | (1 << 62)
                expected_child_uids = [legacy_uid] + [
                    (1 << 60) | (uid << 20) | effect_id
                    for effect_id in expected_ids[1:]
                ]
                self.assertEqual([row[1] for row in display], expected_child_uids)
                self.assertTrue(all(row[2] == 0 for row in display))
                self.assertEqual(
                    [
                        self.frame(opcode, packet)[3]
                        for opcode, packet in packets
                        if opcode == 12613
                    ],
                    [310] + [row[1] for row in definitions],
                )
                for opcode, packet in packets:
                    if opcode == 12613:
                        self.assertEqual(packet[12], 0)  # No child re-execution.
                self.assertEqual(packets[-1], (13420, struct.pack(">i", -1)))

    def test_reconnect_and_quiet_countdown_preserve_icons_without_reapplying_them(self):
        state = self.state(1295, 91_295)
        initial = self.character(state)
        reconnect = snapshot(initial, allocate_action=iter(range(100, 130)).__next__)
        self.assertEqual(
            [row[0] for row in self.native_effects(reconnect, 12613)],
            [row[0] for row in self.GROUPS[1295][1]],
        )

        ticking = self.character(self.state(1295, 91_295, remaining=891_000))
        self.assertEqual(delta(initial, ticking), ())

    def test_refresh_removes_children_in_reverse_then_reapplies_in_native_order(self):
        before = self.character(self.state(1295, 91_295, remaining=400_000))
        after = self.character(self.state(1295, 91_295, remaining=800_000))
        packets = delta(before, after, allocate_action=iter(range(1, 80)).__next__)
        ids = [row[0] for row in self.GROUPS[1295][1]]
        self.assertEqual(
            [row[0] for row in self.native_effects(packets, 13560)], list(reversed(ids))
        )
        self.assertEqual([row[0] for row in self.native_effects(packets, 12613)], ids)
        self.assertEqual(packets[-1], (13420, struct.pack(">i", -1)))

    def test_expiration_removes_all_display_children_and_single_child_keeps_legacy_uid(
        self,
    ):
        before = self.character(self.state(4564, 94_564))
        expired = self.character()
        packets = delta(before, expired, allocate_action=iter(range(1, 40)).__next__)
        expected = [row[0] for row in self.GROUPS[4564][1]]
        self.assertEqual(
            [row[0] for row in self.native_effects(packets, 13560)],
            list(reversed(expected)),
        )

        # Existing single-child consumers retain their historic bit-62 UID.
        one = self.state(3332, 93_332)
        one["metadata"]["native_effects"] = {
            "146149": one["metadata"]["native_effects"]["146149"]
        }
        one["effect_ids"] = [146149]
        # Make the chosen single row explicit to the display selector.
        one["metadata"]["native_visual_effect_ids"] = []
        single_packets = snapshot(
            self.character(one), allocate_action=iter(range(50, 60)).__next__
        )
        self.assertEqual(
            self.native_effects(single_packets, 12613),
            [
                (146149, 93_332 | (1 << 62), 0),
            ],
        )


if __name__ == "__main__":
    unittest.main()
