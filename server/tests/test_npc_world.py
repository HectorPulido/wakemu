import struct
import unittest

from wakfu_server.maps.npc_world import (
    begin,
    decode_interaction,
    nearby,
    spawn,
    validate_placements,
)


class NpcWorldTests(unittest.TestCase):
    def setUp(self):
        self.row = dict(
            actor_id=-2251799813685248,
            reference_id=2986,
            map_id=1134,
            instance_id=0,
            x=-10,
            y=-8,
            z=-1,
            direction=3,
            interaction_range=4,
            dialogue_root=6274,
            action_ids=[515],
            enabled=True,
        )
        self.character = dict(
            id=100, account_id=200, map_id=1134, instance_id=0, x=-12, y=-8, z=-1
        )
        self.native = {
            "nodes": [
                {
                    "id": 6274,
                    "criteria": "",
                    "native_cmT": "npc2986",
                    "choices": [
                        {"id": 14075, "criteria": ""},
                        {"id": 14076, "criteria": "quest_flag"},
                    ],
                }
            ],
            "speakers": [
                {"ref": 2986, "min_level": 0, "max_level": 1, "actions": [{"id": 515}]}
            ],
            "translations": {"es": {"content.7.2986": "Arh Kayuh"}},
        }

    def test_visible_native_actor_packet_and_click_contract(self):
        opcode, body = spawn(self.row, self.native)
        self.assertEqual(opcode, 12608)
        self.assertEqual(body[:3], b"\x00\x01\x01")
        self.assertEqual(struct.unpack_from(">q", body, 3)[0], self.row["actor_id"])
        self.assertIn(b"Arh Kayuh", body)
        self.assertEqual(
            decode_interaction(struct.pack(">qq", self.row["actor_id"], 515)),
            (self.row["actor_id"], 515),
        )
        with self.assertRaises(ValueError):
            decode_interaction(bytes(15))

    def test_initial_dialogue_closes_without_quest_grants(self):
        session, packet = begin(
            lambda: self.character,
            lambda: [self.row],
            self.row["actor_id"],
            515,
            self.native,
        )
        self.assertEqual(packet[0], 12969)
        with self.assertRaises(ValueError):
            session.choose(6274, 14076)
        with self.assertRaises(ValueError):
            session.choose(6274, 99)
        self.assertEqual(session.choose(6274, 14075), (12218, struct.pack(">i", 0)))

    def test_rejects_wrong_instance_distance_or_action_and_rechecks_on_choice(self):
        for changes, action in [({"instance_id": 1}, 515), ({"x": 50}, 515), ({}, 999)]:
            self.character.update(changes)
            with self.assertRaises(ValueError):
                begin(
                    lambda: self.character,
                    lambda: [self.row],
                    self.row["actor_id"],
                    action,
                    self.native,
                )
            self.character.update(map_id=1134, instance_id=0, x=-12)
        session, _ = begin(
            lambda: self.character,
            lambda: [self.row],
            self.row["actor_id"],
            515,
            self.native,
        )
        self.character["instance_id"] = 1
        self.assertFalse(nearby(self.character, self.row))
        with self.assertRaises(ValueError):
            session.choose(6274, 14075)
        self.assertIsNone(session.node_id)

    def test_nearby_platform_npc_remains_reachable_and_is_rechecked(self):
        self.row.update(
            actor_id=-1706442046308339, reference_id=5460, x=0, y=-19, z=3, map_id=1388
        )
        self.character.update(x=0, y=-17, z=0, map_id=1388)
        self.assertTrue(nearby(self.character, self.row))
        self.assertFalse(nearby(self.character, dict(self.row, actor_id=-123)))
        self.assertFalse(nearby(self.character, dict(self.row, z=4)))
        self.character["z"] = -1
        self.assertTrue(nearby(self.character, self.row))
        self.character["z"] = -2
        self.assertFalse(nearby(self.character, self.row))

    def test_dialogue_freezes_owner_identity_across_provider_replacement_and_in_place_mutation(
        self,
    ):
        original = dict(self.character)
        for changed, replace_provider in (
            ({"id": original["id"] + 1}, True),
            ({"id": original["id"] + 1}, False),
            ({"account_id": original["account_id"] + 1}, False),
        ):
            with self.subTest(changed=changed, replace_provider=replace_provider):
                current = [dict(original)]
                session, packet = begin(
                    lambda: current[0],
                    lambda: [self.row],
                    self.row["actor_id"],
                    515,
                    self.native,
                )
                self.assertEqual(packet[0], 12969)
                if replace_provider:
                    current[0] = dict(current[0], **changed)
                else:
                    current[0].update(changed)
                self.assertEqual(
                    {
                        key: current[0][key]
                        for key in ("map_id", "instance_id", "x", "y", "z")
                    },
                    {
                        key: original[key]
                        for key in ("map_id", "instance_id", "x", "y", "z")
                    },
                )
                with self.assertRaises(ValueError):
                    session.choose(6274, 14075)
                self.assertIsNone(session.node_id)
                self.assertIsNone(session.speaker_id)
        # Movement itself must not invalidate an otherwise owned dialogue.
        current = dict(original)
        session, packet = begin(
            lambda: current, lambda: [self.row], self.row["actor_id"], 515, self.native
        )
        self.assertEqual(packet[0], 12969)
        current["x"] += 1
        self.assertTrue(nearby(current, self.row))
        self.assertEqual(session.choose(6274, 14075), (12218, struct.pack(">i", 0)))
        self.assertIsNone(session.node_id)

    def test_rejects_duplicate_identity_positions_and_foreign_native_roots(self):
        for other in [
            dict(self.row),
            dict(self.row, actor_id=self.row["actor_id"] - 1),
            dict(self.row, dialogue_root=99),
        ]:
            with self.assertRaises(ValueError):
                validate_placements([self.row, other], self.native)
        with self.assertRaises(ValueError):
            validate_placements([dict(self.row, action_ids=[999])], self.native)

    def test_entry_criteria_apply_to_root_while_live_placement_and_child_criteria_remain(
        self,
    ):
        from test_npc_observed_dialogue import captured_row
        from unittest.mock import patch
        from wakfu_server.maps import npc_observed_dialogue

        row = captured_row(-1706442046308322, 5461, 1385, -17, -4, 17, 3, 5765, 1243)
        character = dict(
            id=100,
            account_id=200,
            map_id=1385,
            instance_id=0,
            x=-17,
            y=-4,
            z=17,
            level=6,
        )
        native = {
            "nodes": [
                {
                    "id": 5765,
                    "criteria": "not IsAchievementObjectiveComplete(10596)",
                    "native_cmT": "npc5461",
                    "choices": [{"id": 11, "criteria": ""}],
                },
                {
                    "id": 5766,
                    "criteria": "",
                    "native_cmT": "npc5461",
                    "choices": [
                        {"id": 12, "criteria": "IsAchievementObjectiveComplete(10596)"}
                    ],
                },
            ],
            "speakers": [
                {
                    "ref": 5461,
                    "min_level": 1,
                    "max_level": 10,
                    "actions": [{"id": 1243, "criteria": ""}],
                }
            ],
            "translations": {"es": {"content.7.5461": "Otomai"}},
        }
        facts = {10596: False}
        rows = [row]
        with patch.object(
            npc_observed_dialogue,
            "graph",
            return_value={(5765, 11): 5766, (5766, 12): 0},
        ):
            session, _ = begin(
                lambda: character,
                lambda: rows,
                row["actor_id"],
                1243,
                native,
                facts_provider=lambda: facts,
            )
            self.assertEqual(session.choose(5765, 11)[1], struct.pack(">i", 5766))
            facts[10596] = True
            # A quest transition can invalidate the entry guard while the
            # already offered child continuation remains available.
            self.assertEqual(session.choose(5766, 12), (12218, struct.pack(">i", 0)))

            facts[10596] = True
            with self.assertRaises(ValueError):
                begin(
                    lambda: character,
                    lambda: rows,
                    row["actor_id"],
                    1243,
                    native,
                    facts_provider=lambda: facts,
                )

            facts[10596] = False
            session, _ = begin(
                lambda: character,
                lambda: rows,
                row["actor_id"],
                1243,
                native,
                facts_provider=lambda: facts,
            )
            character["x"] = 100
            with self.assertRaises(ValueError):
                session.choose(5765, 11)

            character["x"] = -17
            session, _ = begin(
                lambda: character,
                lambda: rows,
                row["actor_id"],
                1243,
                native,
                facts_provider=lambda: facts,
            )
            rows[0] = dict(row, x=-16)
            with self.assertRaises(ValueError):
                session.choose(5765, 11)
