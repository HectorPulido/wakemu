import struct
import sys
import types
import unittest
from unittest.mock import Mock, patch

from wakfu_server.achievements import rii_free_practice as practice
from wakfu_server.achievements import rii_lesson_visibility as visibility


class FreePracticeTests(unittest.TestCase):
    def test_practice_resistance_metadata_is_excluded_from_native_actor_comparison(
        self,
    ):
        from wakfu_server.combat_fixed_actor_placement import native_member_fields

        actor = {
            "id": -42,
            "ref": 2335,
            "map_id": 1388,
            "instance_id": 0,
            "rii_practice_resistance": 50,
        }
        self.assertEqual(
            native_member_fields(actor),
            {k: v for k, v in actor.items() if k != "rii_practice_resistance"},
        )
        for invalid in (
            {"ref": 42},
            {"map_id": 1},
            {"id": 42},
            {"rii_practice_resistance": 51},
        ):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                native_member_fields({**actor, **invalid})

    def test_owned_resistance_is_applied_to_all_four_combat_elements(self):
        from wakfu_server import combat_actor_snapshot as snapshot

        actor = types.SimpleNamespace(id=-42, controlled=False, effective_level=1)
        catalog = {"npc_profiles": {"2335": {"physical_radius": 0}}}
        monster = {"id": -42, "ref": 2335, "map_id": 1388, "instance_id": 0}
        for percent, expected in practice.RESISTANCE_POINTS.items():
            values = {
                n: {"minimum": -10000, "maximum": 10000, "current": 0}
                for n in (28, 29, 30, 31)
            }
            monster["rii_practice_resistance"] = percent
            with self.subTest(percent=percent), patch.object(
                snapshot, "_fresh"
            ), patch.object(snapshot, "_rows"), patch.object(
                snapshot, "native_npc_creation_values", return_value=values
            ), patch.object(
                snapshot,
                "_finish",
                side_effect=lambda actor, rows, values, **kw: values,
            ):
                result = snapshot.build_npc_snapshot(
                    monster,
                    actor,
                    wp_current=0,
                    wp_maximum=0,
                    running_effects=[],
                    catalog=catalog,
                )
                self.assertEqual(
                    [result[n]["current"] for n in (28, 29, 30, 31)], [expected] * 4
                )

    def test_native_menu_offers_basic_fight_and_multiple_sacks_without_fabricating_variants(
        self,
    ):
        character = {
            "id": 7,
            "account_id": 4,
            "map_id": 1388,
            "instance_id": 0,
            "x": 0,
            "y": -17,
            "z": 0,
        }
        row = {
            "actor_id": practice.ACTOR,
            "reference_id": 5460,
            "map_id": 1388,
            "instance_id": 0,
            "x": 0,
            "y": -19,
            "z": 3,
        }
        nodes = {
            practice.MENU: {
                "id": practice.MENU,
                "criteria": "",
                "choices": [
                    {"id": c, "criteria": ""} for c in (*range(9117, 9127), 12376, 9113)
                ],
            },
            practice.MULTI_MENU: {
                "id": practice.MULTI_MENU,
                "criteria": "",
                "choices": [
                    {"id": c, "criteria": ""}
                    for c in (*range(12369, 12375), 13733, 12375)
                ],
            },
        }
        npc_world = types.ModuleType("wakfu_server.npc_world")
        npc_world.validate_placements = lambda rows: rows
        npc_world.nearby = lambda character, row: True
        npc_protectors = types.ModuleType("wakfu_server.npc_protectors")
        npc_protectors.speaker = lambda row: (2, practice.ACTOR)
        with patch.dict(
            sys.modules,
            {
                "wakfu_server.npc_world": npc_world,
                "wakfu_server.npc_protectors": npc_protectors,
            },
        ), patch(
            "wakfu_server.npc_dialogue.catalog", return_value={"node_index": nodes}
        ):
            session, (opcode, _) = practice.begin_menu(
                lambda: character, lambda: [row], practice.ACTOR, practice.ACTION
            )
            self.assertEqual(opcode, 12969)
            packet, starts = practice.choose_menu(
                session, {"node_id": 3612, "choice_id": 12376}
            )
            self.assertEqual(packet, (12218, struct.pack(">i", 5195)))
            self.assertFalse(starts)
            _, starts = practice.choose_menu(
                session, {"node_id": 5195, "choice_id": 12375}
            )
            self.assertFalse(starts)
            session, _ = practice.begin_menu(
                lambda: character, lambda: [row], practice.ACTOR, practice.ACTION
            )
            packet, starts = practice.choose_menu(
                session, {"node_id": 3612, "choice_id": 9126}
            )
            self.assertEqual(packet, (12218, struct.pack(">i", 0)))
            self.assertTrue(starts)
            for choice, count in ((12369, 2), (12372, 3)):
                session, _ = practice.begin_menu(
                    lambda: character, lambda: [row], practice.ACTOR, practice.ACTION
                )
                practice.choose_menu(session, {"node_id": 3612, "choice_id": 12376})
                packet, actual = practice.choose_menu(
                    session, {"node_id": 5195, "choice_id": choice}
                )
                self.assertEqual(packet, (12218, struct.pack(">i", 0)))
                self.assertEqual(
                    actual,
                    dict(count=count, resistance_percent=0, reference=practice.REF),
                )
            for choice, (count, percent, ref) in practice.PRACTICE_CHOICES.items():
                session, _ = practice.begin_menu(
                    lambda: character, lambda: [row], practice.ACTOR, practice.ACTION
                )
                if choice[0] == practice.MULTI_MENU:
                    practice.choose_menu(
                        session, {"node_id": practice.MENU, "choice_id": 12376}
                    )
                packet, actual = practice.choose_menu(
                    session, {"node_id": choice[0], "choice_id": choice[1]}
                )
                self.assertEqual(packet, (12218, struct.pack(">i", 0)))
                self.assertEqual(
                    actual, dict(count=count, resistance_percent=percent, reference=ref)
                )

    def test_retire_used_requires_exact_lease_and_authenticated_solo_sack(self):
        actor = {"id": -12, "ref": 2335}
        row = {
            "members": [actor],
            "status": "fighting",
            "generation": "g",
            "fight_id": 41,
            "revision": 3,
        }
        receipt = {
            "character_id": 7,
            "event_key": practice.KEY + "12",
            "payload": practice.payload(7, -12),
        }
        db = Mock()
        db.execute.side_effect = [
            Mock(fetchone=Mock(return_value=row)),
            Mock(fetchall=Mock(return_value=[receipt])),
            Mock(rowcount=1),
        ]
        self.assertTrue(
            practice.retire_used(
                db, (1388, 0, 10), fight_id=41, generation="g", revision=3
            )
        )
        self.assertIn("DELETE FROM combat_groups", db.execute.call_args.args[0])

        for changed in (
            {**row, "revision": 4},
            {**row, "members": [{"id": -12, "ref": 5525}]},
        ):
            db = Mock()
            db.execute.return_value.fetchone.return_value = changed
            self.assertFalse(
                practice.retire_used(
                    db, (1388, 0, 10), fight_id=41, generation="g", revision=3
                )
            )
            self.assertFalse(
                any("DELETE" in call.args[0] for call in db.execute.call_args_list)
            )

    def test_retire_used_rejects_forged_receipt_and_other_maps(self):
        db = Mock()
        db.execute.side_effect = [
            Mock(
                fetchone=Mock(
                    return_value={
                        "members": [{"id": -12, "ref": 2335}],
                        "status": "fighting",
                        "generation": "g",
                        "fight_id": 41,
                        "revision": 3,
                    }
                )
            ),
            Mock(
                fetchall=Mock(
                    return_value=[
                        {
                            "character_id": 8,
                            "event_key": practice.KEY + "12",
                            "payload": practice.payload(7, -12),
                        }
                    ]
                )
            ),
        ]
        self.assertFalse(
            practice.retire_used(
                db, (1388, 0, 10), fight_id=41, generation="g", revision=3
            )
        )
        self.assertEqual(db.execute.call_count, 2)
        other = Mock()
        self.assertFalse(
            practice.retire_used(
                other, (1387, 0, 10), fight_id=41, generation="g", revision=3
            )
        )
        other.execute.assert_not_called()

    def test_only_owner_can_enter_practice_and_wire_targets_created_sack(self):
        actor = {"id": -12, "ref": 2335, "x": 0, "y": -15, "z": 0}
        db = Mock()
        db.execute.return_value.fetchall.return_value = [
            {"character_id": 7, "payload": practice.payload(7, -12)}
        ]
        self.assertIsNone(practice.admit(db, 7, [actor]))
        with self.assertRaises(ValueError):
            practice.admit(db, 8, [actor])
        self.assertEqual(
            practice.start_request(actor), struct.pack(">qiihB", -12, 0, -15, 0, 0)
        )

    def test_practice_sack_is_not_replayed_in_world_snapshots(self):
        actor = {"id": -12, "ref": 2335}
        groups = [{"key": (1388, 0, 123), "members": [actor]}]
        db = Mock()
        db.execute.return_value.fetchall.return_value = [
            {
                "character_id": 7,
                "event_key": practice.KEY + "12",
                "payload": practice.payload(7, -12),
            }
        ]
        self.assertEqual(visibility.visible_groups(db, groups, 7), [])
        self.assertEqual(visibility.visible_groups(db, groups, 8), [])
